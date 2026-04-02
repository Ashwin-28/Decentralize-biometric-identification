import * as LocalAuthentication from "expo-local-authentication";
import * as SecureStore from "expo-secure-store";
import CryptoJS from "crypto-js";
import {
  BiometricAuthResult,
  BiometricPromptOptions,
  SensorInfo,
} from "../types";

class BiometricService {
  async getBiometricStatus(): Promise<{
    hasHardware: boolean;
    isEnrolled: boolean;
    hasFingerprint: boolean;
    availableTypes: LocalAuthentication.AuthenticationType[];
  }> {
    try {
      const [hasHardware, isEnrolled, availableTypes] = await Promise.all([
        LocalAuthentication.hasHardwareAsync(),
        LocalAuthentication.isEnrolledAsync(),
        LocalAuthentication.supportedAuthenticationTypesAsync(),
      ]);

      const hasFingerprint = availableTypes.includes(
        LocalAuthentication.AuthenticationType.FINGERPRINT,
      );

      return {
        hasHardware,
        isEnrolled,
        hasFingerprint,
        availableTypes,
      };
    } catch (error) {
      console.error("[BIOMETRIC] Failed to read biometric status:", error);
      return {
        hasHardware: false,
        isEnrolled: false,
        hasFingerprint: false,
        availableTypes: [],
      };
    }
  }

  /**
   * Check if device supports biometric authentication
   */
  async isBiometricAvailable(): Promise<boolean> {
    try {
      const status = await this.getBiometricStatus();
      return status.hasHardware && status.hasFingerprint && status.isEnrolled;
    } catch (error) {
      console.error("[BIOMETRIC] Hardware check failed:", error);
      return false;
    }
  }

  /**
   * Check which biometric types are available
   */
  async getAvailableBiometrics(): Promise<
    LocalAuthentication.AuthenticationType[]
  > {
    try {
      return await LocalAuthentication.supportedAuthenticationTypesAsync();
    } catch (error) {
      console.error("[BIOMETRIC] Failed to get supported types:", error);
      return [];
    }
  }

  /**
   * Initiate biometric authentication (fingerprint scan)
   */
  async authenticate(
    options?: Partial<BiometricPromptOptions>,
  ): Promise<BiometricAuthResult> {
    try {
      const status = await this.getBiometricStatus();
      if (!status.hasHardware) {
        return {
          success: false,
          error: "No biometric hardware detected on this device.",
        };
      }

      if (!status.hasFingerprint) {
        return {
          success: false,
          error:
            "Fingerprint sensor is not available. This app currently requires fingerprint authentication.",
        };
      }

      if (!status.isEnrolled) {
        return {
          success: false,
          error:
            "No fingerprint is enrolled on this phone. Add a fingerprint in Android Settings, then retry.",
        };
      }

      const authenticated = await LocalAuthentication.authenticateAsync({
        promptMessage: options?.title || "Verify Fingerprint",
        cancelLabel: options?.cancelLabel || "Cancel",
        disableDeviceFallback: options?.disableDeviceFallback ?? true,
        fallbackLabel: "Use passcode",
      });

      return {
        success: authenticated.success,
        data: { authenticated: authenticated.success },
        error: authenticated.success
          ? undefined
          : "error" in authenticated
            ? String(authenticated.error)
            : "Biometric authentication failed",
      };
    } catch (error) {
      console.error("[BIOMETRIC] Authentication failed:", error);
      return {
        success: false,
        error: `Authentication error: ${error instanceof Error ? error.message : "Unknown error"}`,
      };
    }
  }

  /**
   * Enroll a new fingerprint
   * @param fingerprintData - Base64 encoded fingerprint image
   * @param userId - User ID for storage
   */
  async enrollFingerprint(
    fingerprintData: string,
    userId: string,
  ): Promise<BiometricAuthResult> {
    try {
      // Generate fingerprint hash
      const hash = this.generateFingerprintHash(fingerprintData);

      // Store encrypted fingerprint hash in secure storage
      await this.storeEncryptedData(`fp_${userId}`, hash);

      console.log("[BIOMETRIC] Fingerprint enrolled successfully");

      return {
        success: true,
        data: {
          hash,
          fingerprintId: userId,
          timestamp: Date.now(),
        },
      };
    } catch (error) {
      console.error("[BIOMETRIC] Enrollment failed:", error);
      return {
        success: false,
        error: `Enrollment error: ${error instanceof Error ? error.message : "Unknown error"}`,
      };
    }
  }

  /**
   * Verify fingerprint against stored hash
   */
  async verifyFingerprint(
    fingerprintData: string,
    userId: string,
  ): Promise<BiometricAuthResult> {
    try {
      const currentHash = this.generateFingerprintHash(fingerprintData);
      const storedHash = await this.retrieveEncryptedData(`fp_${userId}`);

      if (!storedHash) {
        return {
          success: false,
          error: "No fingerprint found for this user",
        };
      }

      // Calculate similarity
      const similarity = this.calculateSimilarity(currentHash, storedHash);
      const isMatch = similarity > 0.85; // 85% similarity threshold

      console.log(
        `[BIOMETRIC] Fingerprint verification - Similarity: ${(similarity * 100).toFixed(2)}%`,
      );

      return {
        success: isMatch,
        data: {
          match: isMatch,
          hash: currentHash,
          confidenceScore: similarity,
          timestamp: Date.now(),
        },
        error: isMatch
          ? undefined
          : `Low confidence score: ${(similarity * 100).toFixed(2)}%`,
      };
    } catch (error) {
      console.error("[BIOMETRIC] Verification failed:", error);
      return {
        success: false,
        error: `Verification error: ${error instanceof Error ? error.message : "Unknown error"}`,
      };
    }
  }

  /**
   * Generate a cryptographic hash of fingerprint data
   */
  private generateFingerprintHash(fingerprintData: string): string {
    // Remove data URL prefix if present
    const cleanData = fingerprintData.replace(
      /^data:image\/[a-zA-Z]+;base64,/,
      "",
    );

    // Generate SHA-256 hash
    const hash = CryptoJS.SHA256(cleanData).toString();

    return hash;
  }

  /**
   * Store data securely in device
   */
  private async storeEncryptedData(key: string, value: string): Promise<void> {
    try {
      // Encrypt before storing
      const encrypted = CryptoJS.AES.encrypt(value, key).toString();
      await SecureStore.setItemAsync(key, encrypted);
    } catch (error) {
      console.error("[SECURE_STORE] Failed to store data:", error);
      throw error;
    }
  }

  /**
   * Retrieve securely stored data
   */
  private async retrieveEncryptedData(key: string): Promise<string | null> {
    try {
      const encrypted = await SecureStore.getItemAsync(key);
      if (!encrypted) return null;

      // Decrypt data
      const decrypted = CryptoJS.AES.decrypt(encrypted, key).toString(
        CryptoJS.enc.Utf8,
      );
      return decrypted;
    } catch (error) {
      console.error("[SECURE_STORE] Failed to retrieve data:", error);
      return null;
    }
  }

  /**
   * Calculate similarity between two hashes (Hamming distance)
   */
  private calculateSimilarity(hash1: string, hash2: string): number {
    if (hash1 === hash2) return 1.0;

    const len = Math.max(hash1.length, hash2.length);
    let distance = 0;

    for (let i = 0; i < len; i++) {
      if ((hash1[i] || "") !== (hash2[i] || "")) {
        distance++;
      }
    }

    return 1 - distance / len;
  }

  /**
   * Get sensor information
   */
  async getSensorInfo(): Promise<SensorInfo> {
    try {
      const available = await this.isBiometricAvailable();
      const types = await this.getAvailableBiometrics();

      return {
        type: "BUILT_IN",
        manufacturer: "Android",
        model: "BiometricPrompt",
        supported:
          available &&
          types.includes(LocalAuthentication.AuthenticationType.FINGERPRINT),
      };
    } catch (error) {
      console.error("[BIOMETRIC] Failed to get sensor info:", error);
      return {
        type: "BUILT_IN",
        manufacturer: "Unknown",
        model: "Unknown",
        supported: false,
      };
    }
  }

  /**
   * Reset user fingerprint data
   */
  async resetFingerprint(userId: string): Promise<boolean> {
    try {
      await SecureStore.deleteItemAsync(`fp_${userId}`);
      console.log("[BIOMETRIC] Fingerprint reset successfully");
      return true;
    } catch (error) {
      console.error("[BIOMETRIC] Failed to reset fingerprint:", error);
      return false;
    }
  }
}

export default new BiometricService();
