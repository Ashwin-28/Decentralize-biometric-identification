import axios, { AxiosInstance, AxiosError } from "axios";
import {
  EnrollmentRequest,
  EnrollmentResponse,
  AuthenticationRequest,
  AuthenticationResponse,
  FingerprintCaptureResponse,
} from "../types";

class APIClient {
  private api: AxiosInstance;

  // Update this to your backend URL
  private BACKEND_URL =
    (globalThis as any)?.process?.env?.EXPO_PUBLIC_BACKEND_URL ||
    "https://biometric-backend-app.kindstone-7b8f6cd7.southeastasia.azurecontainerapps.io/api";

  constructor() {
    this.api = axios.create({
      baseURL: this.BACKEND_URL,
      timeout: 30000,
      headers: {
        "Content-Type": "application/json",
        "User-Agent": "BiometricMobileApp/1.0",
      },
    });

    // Add request interceptor for logging
    this.api.interceptors.request.use(
      (config) => {
        console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`);
        return config;
      },
      (error) => Promise.reject(error),
    );

    // Add response interceptor for error handling
    this.api.interceptors.response.use(
      (response) => {
        console.log(`[API] ✅ ${response.status} ${response.config.url}`);
        return response;
      },
      (error: AxiosError) => {
        console.error(
          `[API] ❌ Error: ${error.response?.status} ${error.config?.url}`,
          error.response?.data,
        );
        return Promise.reject(error);
      },
    );
  }

  /**
   * Check backend connectivity
   */
  async checkConnection(): Promise<boolean> {
    try {
      const response = await this.api.get("/health");
      return ["ok", "healthy"].includes(
        (response.data?.status || "").toLowerCase(),
      );
    } catch (error) {
      console.error("[API] Connection check failed:", error);
      return false;
    }
  }

  /**
   * Enroll fingerprint on blockchain
   */
  async enrollFingerprint(
    data: EnrollmentRequest,
  ): Promise<EnrollmentResponse> {
    try {
      const formData = new FormData();
      formData.append("name", data.name);
      formData.append("email", data.email);
      formData.append("subject_id", data.subjectId);
      formData.append("fingerprint_hash", data.fingerprintHash);
      formData.append("type", "fingerprint");

      // Convert base64 to blob
      const response = await fetch(data.fingerprintImage);
      const blob = await response.blob();
      formData.append("file", blob, "fingerprint.jpg");

      const apiResponse = await this.api.post("/enroll", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      return {
        success: true,
        message: apiResponse.data?.message || "Enrollment successful",
        data: {
          subjectId: apiResponse.data?.subject_id || data.subjectId,
          transactionHash: apiResponse.data?.transaction_hash || "",
          blockNumber: apiResponse.data?.block_number || 0,
          templateCID: apiResponse.data?.template_cid || "",
        },
      };
    } catch (error) {
      const message = this.getErrorMessage(error);
      console.error("[API] Enrollment failed:", message);
      return {
        success: false,
        message: `Enrollment failed: ${message}`,
        data: {
          subjectId: data.subjectId,
          transactionHash: "",
          blockNumber: 0,
          templateCID: "",
        },
      };
    }
  }

  /**
   * Authenticate fingerprint against blockchain records
   */
  async authenticateFingerprint(
    data: AuthenticationRequest,
  ): Promise<AuthenticationResponse> {
    try {
      const formData = new FormData();
      formData.append("subject_id", data.subjectId);
      formData.append("fingerprint_hash", data.fingerprintHash);
      formData.append("type", "fingerprint");

      // Convert base64 to blob
      const response = await fetch(data.fingerprintImage);
      const blob = await response.blob();
      formData.append("file", blob, "fingerprint.jpg");

      const apiResponse = await this.api.post("/authenticate", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      return {
        success: apiResponse.data?.success === true,
        message: apiResponse.data?.message || "Authentication processed",
        data: {
          authenticated: apiResponse.data?.success === true,
          confidenceScore: (Number(apiResponse.data?.confidence) || 0) / 100,
          transactionHash: apiResponse.data?.transaction_hash || "",
          blockNumber: apiResponse.data?.block_number || 0,
        },
      };
    } catch (error) {
      const message = this.getErrorMessage(error);
      console.error("[API] Authentication failed:", message);
      return {
        success: false,
        message: `Authentication failed: ${message}`,
        data: {
          authenticated: false,
          confidenceScore: 0,
          transactionHash: "",
          blockNumber: 0,
        },
      };
    }
  }

  /**
   * Capture fingerprint from backend sensor (if using external sensor)
   */
  async captureFingerprint(): Promise<FingerprintCaptureResponse | null> {
    try {
      const response = await this.api.post(
        "/fingerprint/capture",
        {},
        {
          timeout: 25000,
        },
      );

      return response.data;
    } catch (error) {
      const message = this.getErrorMessage(error);
      console.error("[API] Capture failed:", message);
      return null;
    }
  }

  /**
   * Get blockchain verification status
   */
  async getBlockchainStatus(): Promise<any> {
    try {
      const response = await this.api.get("/blockchain/status");
      return response.data;
    } catch (error) {
      console.error("[API] Failed to get blockchain status:", error);
      return { connected: false };
    }
  }

  /**
   * Get user fingerprint records
   */
  async getUserRecords(subjectId: string): Promise<any> {
    try {
      const response = await this.api.get(`/subjects/${subjectId}`);
      return response.data;
    } catch (error) {
      console.error("[API] Failed to get user records:", error);
      return null;
    }
  }

  /**
   * Get all authentication logs for user
   */
  async getAuthLogs(subjectId: string): Promise<any[]> {
    try {
      const response = await this.api.get(`/auth-logs?subject_id=${subjectId}`);
      return response.data?.logs || [];
    } catch (error) {
      console.error("[API] Failed to get auth logs:", error);
      return [];
    }
  }

  /**
   * Update backend URL (for configuration)
   */
  setBackendURL(url: string): void {
    this.api.defaults.baseURL = url;
    console.log(`[API] Backend URL updated to: ${url}`);
  }

  /**
   * Helper method to extract error message
   */
  private getErrorMessage(error: any): string {
    if (axios.isAxiosError(error)) {
      if (error.response?.data?.error) {
        return error.response.data.error;
      }
      if (error.response?.data?.message) {
        return error.response.data.message;
      }
      if (error.message) {
        return error.message;
      }
    }
    return "Unknown error occurred";
  }
}

export default new APIClient();
