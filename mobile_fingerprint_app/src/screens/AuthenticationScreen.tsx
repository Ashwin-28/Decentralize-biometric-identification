import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  Alert,
  SafeAreaView,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import {
  PrimaryButton,
  SecondaryButton,
  LoadingOverlay,
  StatusBanner,
} from "../components/Button";
import BiometricService from "../services/biometricService";
import APIClient from "../services/apiClient";

type AuthStep = "input" | "scanning" | "verifying" | "result";

export const AuthenticationScreen: React.FC = () => {
  const [step, setStep] = useState<AuthStep>("input");
  const [loading, setLoading] = useState(false);
  const [subjectId, setSubjectId] = useState("");
  const [scanProgress, setScanProgress] = useState(0);
  const [fingerprintCaptured, setFingerprintCaptured] = useState<string | null>(
    null,
  );
  const [fingerprintHash, setFingerprintHash] = useState<string | null>(null);
  const [authResult, setAuthResult] = useState<{
    success: boolean;
    message: string;
    confidenceScore?: number;
    transactionHash?: string;
  } | null>(null);
  const [statusMessage, setStatusMessage] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  useEffect(() => {
    checkBiometricSupport();
  }, []);

  const checkBiometricSupport = async () => {
    const status = await BiometricService.getBiometricStatus();

    if (!status.hasHardware) {
      setStatusMessage({
        type: "error",
        message: "No biometric hardware detected on this device.",
      });
      return;
    }

    if (!status.hasFingerprint) {
      setStatusMessage({
        type: "error",
        message:
          "Fingerprint sensor not detected. This app requires fingerprint.",
      });
      return;
    }

    if (!status.isEnrolled) {
      setStatusMessage({
        type: "error",
        message:
          "No fingerprint enrolled on this phone. Add fingerprint in Android Settings and retry.",
      });
    }
  };

  const generateMockFingerprintImage = async (): Promise<string> => {
    return "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAIBAQIBAQICAgICAgICAwUDAwwDAwYEBAMFBwYHBwcGBwcICQsJCAgKCAcHCg0KCgsMDAwMBwkODw0MDgsMDAz/2wBDAQICAgMDAwYDAwYMCAcIDAwIDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAz/wAARCADIAMgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWm5ybnJ2eoqOkpaanqKmqsrO0tba2uLm6wsPExcbHyMnK0tPU1dbW2Nna4uPk5ebn6Onq8vP09fb2+Pn6/8QAHwEAAwEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba2uLm6wsPExcbHyMnK0tPU1dbW2Nna4uPk5ebn6Onq8vP09fb2+Pn6/9oADAMBAAIRAxEAPwD9/KKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigD/2Q==";
  };

  const handleStartAuthentication = async () => {
    if (!subjectId.trim()) {
      Alert.alert("Error", "Please enter your Subject ID");
      return;
    }

    setStep("scanning");
    setLoading(true);
    setScanProgress(0);

    try {
      // Simulate scanning with progress
      const progressInterval = setInterval(() => {
        setScanProgress((prev) => {
          if (prev >= 100) {
            clearInterval(progressInterval);
            return 100;
          }
          return prev + Math.random() * 25;
        });
      }, 300);

      // Authenticate and capture fingerprint
      const authResult = await BiometricService.authenticate({
        title: "🔍 Verify Fingerprint",
        subtitle: "Authentication",
        description: "Place your finger on the sensor to authenticate",
        cancelLabel: "Cancel",
        disableDeviceFallback: true,
      });

      clearInterval(progressInterval);
      setScanProgress(100);

      if (!authResult.success) {
        throw new Error(authResult.error || "Fingerprint capture failed");
      }

      // Generate mock fingerprint
      const mockFingerprint = await generateMockFingerprintImage();
      setFingerprintCaptured(mockFingerprint);

      // Verify locally
      const verifyResult = await BiometricService.verifyFingerprint(
        mockFingerprint,
        subjectId.trim(),
      );

      if (!verifyResult.success) {
        throw new Error("Local verification failed");
      }

      setFingerprintHash(verifyResult.data?.hash || "");
      setStep("verifying");

      // Continue to blockchain verification
      await handleBlockchainVerification(mockFingerprint);
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error";
      setStatusMessage({
        type: "error",
        message: `❌ ${errorMessage}`,
      });
      setScanProgress(0);
      setStep("input");
    } finally {
      setLoading(false);
    }
  };

  const handleBlockchainVerification = async (fingerprintImage: string) => {
    try {
      const response = await APIClient.authenticateFingerprint({
        subjectId: subjectId.trim(),
        fingerprintImage,
        fingerprintHash: fingerprintHash || "",
      });

      if (response.success && response.data?.authenticated) {
        setAuthResult({
          success: true,
          message: "Authentication Successful! ✅",
          confidenceScore: response.data.confidenceScore,
          transactionHash: response.data.transactionHash,
        });
        setStatusMessage({
          type: "success",
          message: "You have been successfully authenticated",
        });
      } else {
        throw new Error(
          response.message || "Authentication failed on blockchain",
        );
      }

      setStep("result");
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Verification error";
      setAuthResult({
        success: false,
        message: `Authentication Failed: ${errorMessage}`,
      });
      setStatusMessage({
        type: "error",
        message: `❌ ${errorMessage}`,
      });
      setStep("result");
    }
  };

  const handleReset = () => {
    setStep("input");
    setSubjectId("");
    setFingerprintCaptured(null);
    setFingerprintHash(null);
    setAuthResult(null);
    setScanProgress(0);
    setStatusMessage(null);
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        style={styles.flex}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          {/* Header */}
          <LinearGradient
            colors={["#3b82f6", "#2563eb"]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.header}
          >
            <Text style={styles.headerTitle}>🔐 Authentication</Text>
            <Text style={styles.headerSubtitle}>Verify Your Fingerprint</Text>
          </LinearGradient>

          {/* Status Banner */}
          {statusMessage && (
            <StatusBanner
              type={statusMessage.type}
              message={statusMessage.message}
              onDismiss={() => setStatusMessage(null)}
            />
          )}

          {/* Input Step */}
          {step === "input" && (
            <View style={styles.stepContainer}>
              <Text style={styles.stepTitle}>Enter Your Subject ID</Text>

              <View style={styles.formGroup}>
                <Text style={styles.label}>Subject ID *</Text>
                <TextInput
                  style={styles.input}
                  placeholder="YOUR_SUBJECT_ID_HERE"
                  placeholderTextColor="#666"
                  value={subjectId}
                  onChangeText={setSubjectId}
                />
              </View>

              <View style={styles.infoBox}>
                <Text style={styles.infoLabel}>📝 What's a Subject ID?</Text>
                <Text style={styles.infoText}>
                  It's the unique identifier you received during enrollment.
                  Check your enrollment confirmation email.
                </Text>
              </View>

              <PrimaryButton
                onPress={handleStartAuthentication}
                title="Start Authentication"
                icon="🚀"
              />
            </View>
          )}

          {/* Scanning Step */}
          {step === "scanning" && (
            <View style={styles.stepContainer}>
              <View style={styles.scanningBox}>
                <Text style={styles.scanningIcon}>👆</Text>
                <Text style={styles.scanningTitle}>Scanning...</Text>
                <Text style={styles.scanningDescription}>
                  Place your finger on the sensor
                </Text>

                <View style={styles.progressContainer}>
                  <View
                    style={[styles.progressBar, { width: `${scanProgress}%` }]}
                  />
                  <Text style={styles.progressText}>
                    {Math.round(scanProgress)}%
                  </Text>
                </View>
              </View>
            </View>
          )}

          {/* Verifying Step */}
          {step === "verifying" && (
            <View style={styles.stepContainer}>
              <View style={styles.verifyingBox}>
                <Text style={styles.verifyingIcon}>⚙️</Text>
                <Text style={styles.verifyingTitle}>Verifying...</Text>
                <Text style={styles.verifyingDescription}>
                  Comparing with blockchain records
                </Text>
              </View>
            </View>
          )}

          {/* Result Step */}
          {step === "result" && authResult && (
            <View style={styles.stepContainer}>
              {authResult.success ? (
                <View style={styles.successResultBox}>
                  <Text style={styles.resultIcon}>✅</Text>
                  <Text style={styles.resultTitle}>
                    Authentication Successful
                  </Text>
                  <Text style={styles.resultMessage}>
                    Your fingerprint has been verified
                  </Text>

                  <View style={styles.resultDetails}>
                    <View style={styles.detailRow}>
                      <Text style={styles.detailLabel}>Subject ID:</Text>
                      <Text style={styles.detailValue}>{subjectId}</Text>
                    </View>
                    <View style={styles.detailRow}>
                      <Text style={styles.detailLabel}>Confidence:</Text>
                      <Text style={styles.detailValue}>
                        {authResult.confidenceScore
                          ? (authResult.confidenceScore * 100).toFixed(1)
                          : "N/A"}
                        %
                      </Text>
                    </View>
                    {authResult.transactionHash && (
                      <View style={styles.detailRow}>
                        <Text style={styles.detailLabel}>Transaction:</Text>
                        <Text style={styles.detailValue}>
                          {authResult.transactionHash.substring(0, 16)}...
                        </Text>
                      </View>
                    )}
                  </View>

                  <PrimaryButton
                    onPress={handleReset}
                    title="Authenticate Again"
                    icon="🔄"
                  />
                </View>
              ) : (
                <View style={styles.errorResultBox}>
                  <Text style={styles.resultIcon}>❌</Text>
                  <Text style={styles.resultTitle}>Authentication Failed</Text>
                  <Text style={styles.resultMessage}>{authResult.message}</Text>

                  <View style={styles.errorTips}>
                    <Text style={styles.tipsLabel}>💡 Tips to try again:</Text>
                    <Text style={styles.tipText}>
                      • Ensure your finger is clean and dry
                    </Text>
                    <Text style={styles.tipText}>
                      • Make sure Subject ID is correct
                    </Text>
                    <Text style={styles.tipText}>
                      • Check your internet connection
                    </Text>
                  </View>

                  <PrimaryButton
                    onPress={handleReset}
                    title="Try Again"
                    icon="🔄"
                  />
                </View>
              )}
            </View>
          )}
        </ScrollView>
      </KeyboardAvoidingView>

      <LoadingOverlay visible={loading} message="Processing..." />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#050505",
  },
  flex: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 20,
  },
  header: {
    paddingVertical: 24,
    paddingHorizontal: 16,
    marginBottom: 16,
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: "700",
    color: "#fff",
    marginBottom: 4,
  },
  headerSubtitle: {
    fontSize: 14,
    color: "#ccc",
    opacity: 0.8,
  },
  stepContainer: {
    paddingHorizontal: 16,
    paddingVertical: 20,
  },
  stepTitle: {
    fontSize: 20,
    fontWeight: "700",
    color: "#3b82f6",
    marginBottom: 12,
  },
  formGroup: {
    marginBottom: 16,
  },
  label: {
    fontSize: 13,
    fontWeight: "600",
    color: "#3b82f6",
    marginBottom: 8,
  },
  input: {
    backgroundColor: "#1a1a1a",
    borderWidth: 1,
    borderColor: "#3b82f6",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 12,
    fontSize: 14,
    color: "#fff",
  },
  infoBox: {
    backgroundColor: "#1a1a1a",
    borderLeftWidth: 3,
    borderLeftColor: "#3b82f6",
    padding: 16,
    borderRadius: 8,
    marginBottom: 16,
  },
  infoLabel: {
    fontSize: 13,
    fontWeight: "600",
    color: "#3b82f6",
    marginBottom: 8,
  },
  infoText: {
    fontSize: 12,
    color: "#888",
    lineHeight: 18,
  },
  scanningBox: {
    backgroundColor: "#1a1a1a",
    borderWidth: 2,
    borderColor: "#3b82f6",
    borderRadius: 12,
    padding: 40,
    marginBottom: 16,
    alignItems: "center",
  },
  scanningIcon: {
    fontSize: 64,
    marginBottom: 16,
  },
  scanningTitle: {
    fontSize: 20,
    fontWeight: "600",
    color: "#3b82f6",
    marginBottom: 8,
  },
  scanningDescription: {
    fontSize: 13,
    color: "#888",
    marginBottom: 24,
  },
  progressContainer: {
    width: "100%",
    height: 8,
    backgroundColor: "#0a0a0a",
    borderRadius: 4,
    overflow: "hidden",
  },
  progressBar: {
    height: "100%",
    backgroundColor: "#3b82f6",
    borderRadius: 4,
  },
  progressText: {
    fontSize: 12,
    color: "#3b82f6",
    marginTop: 8,
    fontWeight: "600",
  },
  verifyingBox: {
    backgroundColor: "#1a1a1a",
    borderWidth: 2,
    borderColor: "#3b82f6",
    borderRadius: 12,
    padding: 40,
    alignItems: "center",
  },
  verifyingIcon: {
    fontSize: 48,
    marginBottom: 16,
    opacity: 0.6,
  },
  verifyingTitle: {
    fontSize: 18,
    fontWeight: "600",
    color: "#3b82f6",
    marginBottom: 8,
  },
  verifyingDescription: {
    fontSize: 13,
    color: "#888",
  },
  successResultBox: {
    backgroundColor: "#1a1a1a",
    borderWidth: 2,
    borderColor: "#10b981",
    borderRadius: 12,
    padding: 24,
    alignItems: "center",
  },
  errorResultBox: {
    backgroundColor: "#1a1a1a",
    borderWidth: 2,
    borderColor: "#ef4444",
    borderRadius: 12,
    padding: 24,
    alignItems: "center",
  },
  resultIcon: {
    fontSize: 56,
    marginBottom: 12,
  },
  resultTitle: {
    fontSize: 20,
    fontWeight: "700",
    color: "#fff",
    marginBottom: 8,
  },
  resultMessage: {
    fontSize: 14,
    color: "#aaa",
    marginBottom: 20,
    textAlign: "center",
  },
  resultDetails: {
    width: "100%",
    backgroundColor: "#0a0a0a",
    borderRadius: 8,
    padding: 16,
    marginBottom: 20,
  },
  detailRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: "#2a2a2a",
  },
  detailLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: "#3b82f6",
  },
  detailValue: {
    fontSize: 12,
    color: "#888",
  },
  errorTips: {
    width: "100%",
    backgroundColor: "#0a0a0a",
    borderRadius: 8,
    padding: 16,
    marginBottom: 20,
  },
  tipsLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: "#ef4444",
    marginBottom: 8,
  },
  tipText: {
    fontSize: 11,
    color: "#888",
    marginBottom: 4,
  },
});
