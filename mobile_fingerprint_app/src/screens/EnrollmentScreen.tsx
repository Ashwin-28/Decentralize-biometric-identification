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

type EnrollmentStep = "info" | "details" | "capture" | "verify" | "success";

export const EnrollmentScreen: React.FC = () => {
  const [step, setStep] = useState<EnrollmentStep>("info");
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [fingerprintCaptured, setFingerprintCaptured] = useState<string | null>(
    null,
  );
  const [fingerprintHash, setFingerprintHash] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);
  const [scanProgress, setScanProgress] = useState(0);

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

  const generateSubjectId = () => {
    return `USER_${Date.now()}_${Math.random().toString(36).substring(7).toUpperCase()}`;
  };

  const handleContinueDetails = async () => {
    if (!name.trim() || !email.trim()) {
      Alert.alert("Error", "Please fill in all fields");
      return;
    }

    // Generate subject ID if not provided
    if (!subjectId.trim()) {
      setSubjectId(generateSubjectId());
    }

    setStep("capture");
  };

  const handleCaptureFingerprintClick = async () => {
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
        title: "🔍 Capture Fingerprint",
        subtitle: "Enrollment Scan",
        description: "Place your finger on the sensor",
        cancelLabel: "Cancel",
        disableDeviceFallback: true,
      });

      clearInterval(progressInterval);
      setScanProgress(100);

      if (!authResult.success) {
        throw new Error(authResult.error || "Fingerprint capture failed");
      }

      // Generate mock fingerprint image (in production, this would come from camera)
      const mockFingerprint = await generateMockFingerprintImage();
      setFingerprintCaptured(mockFingerprint);

      // Enroll locally
      const enrollResult = await BiometricService.enrollFingerprint(
        mockFingerprint,
        subjectId || generateSubjectId(),
      );

      if (enrollResult.success && enrollResult.data?.hash) {
        setFingerprintHash(enrollResult.data.hash);
        setStatusMessage({
          type: "success",
          message: "✅ Fingerprint captured successfully",
        });
        setTimeout(() => setStep("verify"), 1500);
      } else {
        throw new Error("Failed to generate fingerprint hash");
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error";
      setStatusMessage({
        type: "error",
        message: `❌ ${errorMessage}`,
      });
      console.error("[ENROLL] Capture error:", error);
    } finally {
      setScanProgress(0);
      setLoading(false);
    }
  };

  const handleVerifyAndEnroll = async () => {
    if (!fingerprintHash || !fingerprintCaptured) {
      Alert.alert("Error", "Fingerprint not captured. Please try again.");
      return;
    }

    setLoading(true);

    try {
      // Verify fingerprint locally first
      const verifyResult = await BiometricService.verifyFingerprint(
        fingerprintCaptured,
        subjectId || generateSubjectId(),
      );

      if (!verifyResult.success) {
        throw new Error(
          "Local verification failed. Please try enrolling again.",
        );
      }

      // Then enroll on blockchain
      const enrollResponse = await APIClient.enrollFingerprint({
        name: name.trim(),
        email: email.trim(),
        subjectId: subjectId || generateSubjectId(),
        fingerprintImage: fingerprintCaptured,
        fingerprintHash: fingerprintHash,
        sensorType: "ANDROID_BIOMETRIC",
      });

      if (!enrollResponse.success) {
        throw new Error(
          enrollResponse.message || "Blockchain enrollment failed",
        );
      }

      // Backend returns the canonical subject_id that must be used for authentication.
      if (enrollResponse.data?.subjectId) {
        setSubjectId(enrollResponse.data.subjectId);
      }

      setStatusMessage({
        type: "success",
        message: "✅ Successfully enrolled on blockchain!",
      });

      setTimeout(() => {
        setStep("success");
      }, 2000);
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Enrollment failed";
      setStatusMessage({
        type: "error",
        message: `❌ ${errorMessage}`,
      });
      console.error("[ENROLL] Blockchain error:", error);
    } finally {
      setLoading(false);
    }
  };

  const generateMockFingerprintImage = async (): Promise<string> => {
    // In production, capture from camera or sensor
    // This is a mock blue gradient image
    return "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAIBAQIBAQICAgICAgICAwUDAwwDAwYEBAMFBwYHBwcGBwcICQsJCAgKCAcHCg0KCgsMDAwMBwkODw0MDgsMDAz/2wBDAQICAgMDAwYDAwYMCAcIDAwIDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAz/wAARCADIAMgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWm5ybnJ2eoqOkpaanqKmqsrO0tba2uLm6wsPExcbHyMnK0tPU1dbW2Nna4uPk5ebn6Onq8vP09fb2+Pn6/8QAHwEAAwEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba2uLm6wsPExcbHyMnK0tPU1dbW2Nna4uPk5ebn6Onq8vP09fb2+Pn6/9oADAMBAAIRAxEAPwD9/KKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigD/2Q==";
  };

  const handleReset = () => {
    setStep("info");
    setName("");
    setEmail("");
    setSubjectId("");
    setFingerprintCaptured(null);
    setFingerprintHash(null);
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
            colors={["#c5a059", "#b8944e"]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.header}
          >
            <Text style={styles.headerTitle}>📋 Fingerprint Enrollment</Text>
            <Text style={styles.headerSubtitle}>
              Register Your Biometric Identity
            </Text>
          </LinearGradient>

          {/* Status Banner */}
          {statusMessage && (
            <StatusBanner
              type={statusMessage.type}
              message={statusMessage.message}
              onDismiss={() => setStatusMessage(null)}
            />
          )}

          {/* Step Content */}
          {step === "info" && (
            <View style={styles.stepContainer}>
              <Text style={styles.stepTitle}>
                Welcome to Biometric Enrollment
              </Text>
              <Text style={styles.stepDescription}>
                We'll help you register your fingerprint on the blockchain. This
                process is secure and takes just a few minutes.
              </Text>

              <View style={styles.infoBox}>
                <Text style={styles.infoLabel}>✅ What You'll Need:</Text>
                <Text style={styles.infoText}>• Your fingerprint</Text>
                <Text style={styles.infoText}>• Internet connection</Text>
                <Text style={styles.infoText}>
                  • A few minutes of your time
                </Text>
              </View>

              <View style={styles.infoBox}>
                <Text style={styles.infoLabel}>🔐 Your Privacy:</Text>
                <Text style={styles.infoText}>
                  • Fingerprints are encrypted
                </Text>
                <Text style={styles.infoText}>
                  • Stored on blockchain securely
                </Text>
                <Text style={styles.infoText}>• Only you can authenticate</Text>
              </View>

              <PrimaryButton
                onPress={() => setStep("details")}
                title="Begin Enrollment"
                icon="🚀"
              />
            </View>
          )}

          {step === "details" && (
            <View style={styles.stepContainer}>
              <Text style={styles.stepTitle}>Your Information</Text>

              <View style={styles.formGroup}>
                <Text style={styles.label}>Full Name *</Text>
                <TextInput
                  style={styles.input}
                  placeholder="Enter your full name"
                  placeholderTextColor="#666"
                  value={name}
                  onChangeText={setName}
                />
              </View>

              <View style={styles.formGroup}>
                <Text style={styles.label}>Email Address *</Text>
                <TextInput
                  style={styles.input}
                  placeholder="your@email.com"
                  placeholderTextColor="#666"
                  value={email}
                  onChangeText={setEmail}
                  keyboardType="email-address"
                />
              </View>

              <View style={styles.formGroup}>
                <Text style={styles.label}>Subject ID (Auto-generated)</Text>
                <TextInput
                  style={[styles.input, styles.disabledInput]}
                  value={subjectId || "Will be generated"}
                  editable={false}
                  placeholderTextColor="#666"
                />
              </View>

              <PrimaryButton
                onPress={handleContinueDetails}
                title="Continue"
                icon="➜"
              />
              <SecondaryButton onPress={handleReset} title="Cancel" />
            </View>
          )}

          {step === "capture" && (
            <View style={styles.stepContainer}>
              <Text style={styles.stepTitle}>Capture Your Fingerprint</Text>

              <View style={styles.captureBox}>
                <Text style={styles.captureTitle}>👆 Ready to Scan</Text>
                <Text style={styles.captureDescription}>
                  Place your finger on the device's sensor when prompted
                </Text>

                {scanProgress > 0 && (
                  <View style={styles.progressContainer}>
                    <View
                      style={[
                        styles.progressBar,
                        { width: `${scanProgress}%` },
                      ]}
                    />
                    <Text style={styles.progressText}>
                      {Math.round(scanProgress)}%
                    </Text>
                  </View>
                )}

                <PrimaryButton
                  onPress={handleCaptureFingerprintClick}
                  title="Start Fingerprint Scan"
                  loading={loading}
                  icon="🔍"
                />
              </View>

              <SecondaryButton
                onPress={() => setStep("details")}
                title="Back"
              />
            </View>
          )}

          {step === "verify" && (
            <View style={styles.stepContainer}>
              <Text style={styles.stepTitle}>Verify & Enroll</Text>

              <View style={styles.successBox}>
                <Text style={styles.successIcon}>✅</Text>
                <Text style={styles.successMessage}>Fingerprint Captured!</Text>
                <Text style={styles.successDescription}>
                  Hash: {fingerprintHash?.substring(0, 16)}...
                </Text>
              </View>

              <View style={styles.verifyInfo}>
                <Text style={styles.verifyLabel}>
                  Ready to Enroll on Blockchain?
                </Text>
                <Text style={styles.verifyText}>
                  Your fingerprint data will be securely stored on the
                  blockchain.
                </Text>
              </View>

              <PrimaryButton
                onPress={handleVerifyAndEnroll}
                title="Confirm & Enroll"
                loading={loading}
                icon="🔗"
              />
              <SecondaryButton
                onPress={() => setStep("capture")}
                title="Retake Fingerprint"
              />
            </View>
          )}

          {step === "success" && (
            <View style={styles.stepContainer}>
              <View style={styles.successContainer}>
                <Text style={styles.successIcon}>🎉</Text>
                <Text style={styles.successTitle}>Enrollment Complete!</Text>
                <Text style={styles.successText}>
                  Your fingerprint has been successfully registered on the
                  blockchain.
                </Text>

                <View style={styles.summaryBox}>
                  <Text style={styles.summaryLabel}>Name:</Text>
                  <Text style={styles.summaryValue}>{name}</Text>
                  <Text style={styles.summaryLabel}>Email:</Text>
                  <Text style={styles.summaryValue}>{email}</Text>
                  <Text style={styles.summaryLabel}>Subject ID:</Text>
                  <Text style={styles.summaryValue}>{subjectId}</Text>
                </View>

                <PrimaryButton
                  onPress={handleReset}
                  title="New Enrollment"
                  icon="🔄"
                />
              </View>
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
    color: "#050505",
    marginBottom: 4,
  },
  headerSubtitle: {
    fontSize: 14,
    color: "#1a1a1a",
    opacity: 0.8,
  },
  stepContainer: {
    paddingHorizontal: 16,
    paddingVertical: 20,
  },
  stepTitle: {
    fontSize: 20,
    fontWeight: "700",
    color: "#c5a059",
    marginBottom: 12,
  },
  stepDescription: {
    fontSize: 14,
    color: "#aaa",
    marginBottom: 20,
    lineHeight: 20,
  },
  infoBox: {
    backgroundColor: "#1a1a1a",
    borderLeftWidth: 3,
    borderLeftColor: "#c5a059",
    padding: 16,
    borderRadius: 8,
    marginBottom: 12,
  },
  infoLabel: {
    fontSize: 13,
    fontWeight: "600",
    color: "#c5a059",
    marginBottom: 8,
  },
  infoText: {
    fontSize: 12,
    color: "#888",
    marginBottom: 4,
  },
  formGroup: {
    marginBottom: 16,
  },
  label: {
    fontSize: 13,
    fontWeight: "600",
    color: "#c5a059",
    marginBottom: 8,
  },
  input: {
    backgroundColor: "#1a1a1a",
    borderWidth: 1,
    borderColor: "#c5a059",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 12,
    fontSize: 14,
    color: "#fff",
  },
  disabledInput: {
    backgroundColor: "#0a0a0a",
    opacity: 0.6,
  },
  captureBox: {
    backgroundColor: "#1a1a1a",
    borderWidth: 2,
    borderColor: "#c5a059",
    borderRadius: 12,
    padding: 24,
    marginBottom: 16,
    alignItems: "center",
  },
  captureTitle: {
    fontSize: 18,
    fontWeight: "600",
    color: "#c5a059",
    marginBottom: 8,
  },
  captureDescription: {
    fontSize: 12,
    color: "#888",
    marginBottom: 20,
    textAlign: "center",
  },
  progressContainer: {
    width: "100%",
    height: 6,
    backgroundColor: "#0a0a0a",
    borderRadius: 3,
    marginBottom: 16,
    overflow: "hidden",
  },
  progressBar: {
    height: "100%",
    backgroundColor: "#c5a059",
    borderRadius: 3,
  },
  progressText: {
    fontSize: 12,
    color: "#c5a059",
    marginTop: 4,
    fontWeight: "600",
  },
  successBox: {
    backgroundColor: "#1a1a1a",
    borderWidth: 2,
    borderColor: "#10b981",
    borderRadius: 12,
    padding: 24,
    marginBottom: 16,
    alignItems: "center",
  },
  successIcon: {
    fontSize: 48,
    marginBottom: 12,
  },
  successMessage: {
    fontSize: 18,
    fontWeight: "600",
    color: "#10b981",
    marginBottom: 8,
  },
  successDescription: {
    fontSize: 12,
    color: "#888",
  },
  verifyInfo: {
    backgroundColor: "#0a0a0a",
    padding: 16,
    borderRadius: 8,
    marginBottom: 16,
  },
  verifyLabel: {
    fontSize: 13,
    fontWeight: "600",
    color: "#c5a059",
    marginBottom: 8,
  },
  verifyText: {
    fontSize: 12,
    color: "#888",
    lineHeight: 18,
  },
  successContainer: {
    alignItems: "center",
  },
  successTitle: {
    fontSize: 24,
    fontWeight: "700",
    color: "#10b981",
    marginBottom: 12,
    marginTop: 12,
  },
  successText: {
    fontSize: 14,
    color: "#aaa",
    marginBottom: 24,
    textAlign: "center",
  },
  summaryBox: {
    backgroundColor: "#1a1a1a",
    borderWidth: 1,
    borderColor: "#c5a059",
    borderRadius: 8,
    padding: 16,
    marginBottom: 24,
    width: "100%",
  },
  summaryLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: "#c5a059",
    marginTop: 8,
  },
  summaryValue: {
    fontSize: 13,
    color: "#888",
    marginBottom: 4,
  },
});
