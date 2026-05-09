import axios from "axios";

export const API_FALLBACK = "http://127.0.0.1:5000/api";

const normalizeApiBase = (rawValue) => {
  const input = (rawValue || "").trim();
  if (!input) return API_FALLBACK;

  // Reject relative URLs like "/api" to prevent static-site origin calls.
  if (input.startsWith("/")) return API_FALLBACK;

  try {
    const parsed = new URL(input);
    if (parsed.hostname.endsWith("web.core.windows.net")) {
      return API_FALLBACK;
    }
    const normalized = input.replace(/\/+$/, "");
    return normalized.endsWith("/api") ? normalized : `${normalized}/api`;
  } catch {
    return API_FALLBACK;
  }
};

const runtimeApiUrl =
  typeof window !== "undefined" && window.__APP_CONFIG__?.apiUrl
    ? window.__APP_CONFIG__.apiUrl
    : undefined;

export const API_BASE = normalizeApiBase(
  runtimeApiUrl || process.env.REACT_APP_API_URL,
);

const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

// Health & Status
export const checkHealth = async () => {
  const response = await api.get("/health");
  return response.data;
};

export const getBlockchainStatus = async () => {
  try {
    const response = await api.get("/blockchain/status");
    return response.data;
  } catch {
    return { connected: false };
  }
};

// Biometric Operations
export const extractBiometric = async (file, type = "facial") => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("type", type);
  const response = await api.post("/biometric/extract", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
};

export const checkLiveness = async (file) => {
  const formData = new FormData();
  formData.append("file", file);
  const response = await api.post("/biometric/liveness", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
};

// ── Enrollment ──
// eye_side: 'left' | 'right' | null (only used when type === 'iris')
export const enrollSubject = async (
  file,
  name,
  type = "facial",
  eye_side = null,
  fingerprint_hash = null,
  spoken_password = null,
) => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("name", name);
  formData.append("type", type);
  if (eye_side) formData.append("eye_side", eye_side);
  if (fingerprint_hash) formData.append("fingerprint_hash", fingerprint_hash);
  if (spoken_password) formData.append("spoken_password", spoken_password);
  const response = await api.post("/enroll", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
};

// ── Authentication ──
// eye_side: 'left' | 'right' | null (only used when type === 'iris')
export const authenticateSubject = async (
  file,
  subjectId,
  type = "facial",
  eye_side = null,
  fingerprint_hash = null,
  spoken_password = null,
) => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("subject_id", subjectId);
  formData.append("type", type);
  if (eye_side) formData.append("eye_side", eye_side);
  if (fingerprint_hash) formData.append("fingerprint_hash", fingerprint_hash);
  if (spoken_password) formData.append("spoken_password", spoken_password);
  const response = await api.post("/authenticate", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
};

// Verification (1:1 comparison)
export const verifyBiometrics = async (file1, file2, type = "facial") => {
  const formData = new FormData();
  formData.append("file1", file1);
  formData.append("file2", file2);
  formData.append("type", type);
  const response = await api.post("/verify", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
};

// Statistics
export const getStats = async () => {
  const response = await api.get("/stats");
  return response.data;
};

// Database Explorer
export const getSubjects = async () => {
  const response = await api.get("/subjects");
  return response.data;
};

export const getAuthLogs = async () => {
  const response = await api.get("/auth-logs");
  return response.data;
};

// Blockchain Explorer
export const getBlockchainData = async () => {
  try {
    const response = await api.get("/blockchain/explorer");
    return response.data;
  } catch {
    return { blocks: [], transactions: [], accounts: [] };
  }
};

// ══════════════════════════════════════════════════════════
//  ZKP (Zero-Knowledge Proof) API
// ══════════════════════════════════════════════════════════
export const getZKPStatus = async () => {
  try {
    const response = await api.get("/zkp/status");
    return response.data;
  } catch {
    return { available: false };
  }
};

export const createZKPCommitment = async (file, type = "facial") => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("type", type);
  const response = await api.post("/zkp/commitment", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
};

export const zkpEnroll = async (file, name, type = "facial") => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("name", name);
  formData.append("type", type);
  const response = await api.post("/zkp/enroll", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
};

export const zkpAuthenticate = async (file, subjectId, type = "facial") => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("subject_id", subjectId);
  formData.append("type", type);
  const response = await api.post("/zkp/authenticate", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
};

export const verifyZKPProof = async (proof, commitment) => {
  const response = await api.post("/zkp/verify-proof", { proof, commitment });
  return response.data;
};

// ══════════════════════════════════════════════════════════
//  IPFS API
// ══════════════════════════════════════════════════════════
export const getIPFSStatus = async () => {
  const response = await api.get("/ipfs/status");
  return response.data;
};

export const getIPFSObjects = async () => {
  const response = await api.get("/ipfs/objects");
  return response.data;
};

export const ipfsCat = async (cid) => {
  const response = await api.get(`/ipfs/cat/${cid}`);
  return response.data;
};

// ══════════════════════════════════════════════════════════
//  MULTIMODAL FACE + IRIS API
// ══════════════════════════════════════════════════════════
export const multimodalEnroll = async (
  faceFile,
  irisFile,
  name,
  eye_side = "left",
) => {
  const formData = new FormData();
  formData.append("face_file", faceFile);
  formData.append("voice_file", irisFile);
  formData.append("name", name);
  formData.append("eye_side", eye_side);
  const response = await api.post("/multimodal/enroll", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
};

export const multimodalAuthenticate = async (
  faceFile,
  irisFile,
  subjectId,
  eye_side = "left",
) => {
  const formData = new FormData();
  formData.append("face_file", faceFile);
  formData.append("voice_file", irisFile);
  formData.append("subject_id", subjectId);
  formData.append("eye_side", eye_side);
  const response = await api.post("/multimodal/authenticate", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
};

export const captureFingerprint = async (signal) => {
  const response = await api.post("/fingerprint/capture", {}, { signal });
  return response.data;
};

export const webauthnRegisterOptions = async (name, email = null) => {
  const response = await api.post("/webauthn/register/options", {
    name,
    email,
  });
  return response.data;
};

export const webauthnRegisterVerify = async (
  token,
  name,
  credential,
  email = null,
) => {
  const response = await api.post("/webauthn/register/verify", {
    token,
    name,
    email,
    credential,
  });
  return response.data;
};

export const webauthnAuthenticateOptions = async (identifier) => {
  const response = await api.post("/webauthn/authenticate/options", {
    subject_id: identifier,
  });
  return response.data;
};

export const webauthnAuthenticateVerify = async (token, credential) => {
  const response = await api.post("/webauthn/authenticate/verify", {
    token,
    credential,
  });
  return response.data;
};

export default api;
