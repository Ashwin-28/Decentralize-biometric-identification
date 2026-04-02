// Types for the Biometric Mobile App

export interface BiometricUser {
  subjectId: string;
  name: string;
  email: string;
  fingerprintHash?: string;
  enrolledAt?: number;
  blockchainAddress?: string;
}

export interface FingerprintCaptureResponse {
  success: boolean;
  image_b64: string;
  hash: string;
  simulated: boolean;
  timestamp: number;
}

export interface EnrollmentRequest {
  name: string;
  email: string;
  subjectId: string;
  fingerprintImage: string;
  fingerprintHash: string;
  sensorType: string;
}

export interface EnrollmentResponse {
  success: boolean;
  message: string;
  data: {
    subjectId: string;
    transactionHash: string;
    blockNumber: number;
    templateCID: string;
  };
}

export interface AuthenticationRequest {
  subjectId: string;
  fingerprintImage: string;
  fingerprintHash: string;
}

export interface AuthenticationResponse {
  success: boolean;
  message: string;
  data: {
    authenticated: boolean;
    confidenceScore: number;
    transactionHash: string;
    blockNumber: number;
  };
}

export interface BiometricPromptOptions {
  title: string;
  subtitle: string;
  description: string;
  cancelLabel: string;
  disableDeviceFallback: boolean;
}

export interface BiometricAuthResult {
  success: boolean;
  data?: any;
  error?: string;
}

export interface SensorInfo {
  type: "BUILT_IN" | "EXTERNAL_USB" | "BLUETOOTH";
  manufacturer: string;
  model: string;
  supported: boolean;
}
