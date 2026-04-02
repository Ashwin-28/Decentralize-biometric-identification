import React, { useState, useRef, useEffect } from "react";
import Webcam from "react-webcam";
import { API_BASE } from "../services/api";
import { cropBiometricImage } from "../utils/imageCapture";
import "./ZKPAuthentication.css";

const ZKPAuthentication = () => {
  const [step, setStep] = useState(1);
  const [subjectId, setSubjectId] = useState("");
  const [biometricType, setBiometricType] = useState("facial");
  const [eyeSide, setEyeSide] = useState("left");
  const [, setCapturedImage] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSensorCapturing, setIsSensorCapturing] = useState(false);
  const [proofProgress, setProofProgress] = useState(0);
  const [verificationResult, setVerificationResult] = useState(null);
  const [error, setError] = useState(null);
  const [zkpStatus, setZkpStatus] = useState({ available: false });

  const webcamRef = useRef(null);

  const isFingerprint = biometricType === "fingerprint";
  const isIris = biometricType === "iris";

  useEffect(() => {
    fetch(`${API_BASE}/zkp/status`)
      .then((res) => res.json())
      .then((data) => setZkpStatus(data))
      .catch(() => setZkpStatus({ available: false }));
  }, []);

  useEffect(() => {
    if (isProcessing && proofProgress < 90) {
      const interval = setInterval(() => {
        setProofProgress((prev) => Math.min(prev + 5, 90));
      }, 100);
      return () => clearInterval(interval);
    }
  }, [isProcessing, proofProgress]);

  const runZKPAuth = async (imageB64) => {
    const response = await fetch(imageB64);
    const blob = await response.blob();
    const formData = new FormData();
    formData.append("file", blob, "capture.jpg");
    formData.append("subject_id", subjectId);
    formData.append("type", biometricType);
    if (isIris) formData.append("eye_side", eyeSide);

    const authResponse = await fetch(`${API_BASE}/zkp/authenticate`, {
      method: "POST",
      body: formData,
    });
    return authResponse.json();
  };

  // Webcam capture (face / iris)
  const handleCapture = async () => {
    const imageSrc = webcamRef.current.getScreenshot();
    if (!imageSrc) return;

    let processedImage = imageSrc;
    try {
      processedImage = await cropBiometricImage(
        imageSrc,
        biometricType,
        eyeSide,
      );
    } catch (err) {
      console.error("ZKP crop failed:", err);
    }

    setCapturedImage(processedImage);
    setStep(3);
    setIsProcessing(true);
    setProofProgress(0);
    setError(null);

    try {
      const result = await runZKPAuth(processedImage);
      setProofProgress(100);
      setIsProcessing(false);
      setStep(4);
      setVerificationResult(
        result.error
          ? { success: false, message: result.error }
          : {
              success: result.authenticated,
              message: result.message,
              proof: result.proof,
              verification: result.verification,
              similarity: result.similarity,
              privacy: result.privacy,
              subjectName: result.subject_name,
            },
      );
    } catch (err) {
      setIsProcessing(false);
      setStep(4);
      setVerificationResult({
        success: false,
        message: `Error: ${err.message}`,
      });
    }
  };

  // Sensor capture (fingerprint)
  const handleSensorCapture = async () => {
    setIsSensorCapturing(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/fingerprint/capture`, {
        method: "POST",
      });
      const data = await res.json();
      if (!data.success || !data.image_b64) {
        setError(
          data.error ||
            "Sensor capture failed. Ensure Windows Biometric Service is running.",
        );
        setIsSensorCapturing(false);
        return;
      }

      const imageB64 = `data:image/png;base64,${data.image_b64}`;
      setCapturedImage(imageB64);
      setIsSensorCapturing(false);
      setStep(3);
      setIsProcessing(true);
      setProofProgress(0);

      const result = await runZKPAuth(imageB64);
      setProofProgress(100);
      setIsProcessing(false);
      setStep(4);
      setVerificationResult(
        result.error
          ? { success: false, message: result.error }
          : {
              success: result.authenticated,
              message: result.message,
              proof: result.proof,
              similarity: result.similarity,
              privacy: result.privacy,
              subjectName: result.subject_name,
            },
      );
    } catch (err) {
      setIsSensorCapturing(false);
      setStep(4);
      setVerificationResult({
        success: false,
        message: `Error: ${err.message}`,
      });
    }
  };

  const reset = () => {
    setStep(1);
    setSubjectId("");
    setCapturedImage(null);
    setIsProcessing(false);
    setProofProgress(0);
    setVerificationResult(null);
    setError(null);
  };

  const getBiometricIcon = (t) =>
    ({ facial: "👤", fingerprint: "👆", iris: "👁️" })[t] || "🔍";

  return (
    <div className="zkp-container">
      <div className="glass-header">
        <h1>Zero-Knowledge Proof Authentication</h1>
        <p>Verify your identity without revealing your biometric data</p>
        {zkpStatus.available && (
          <div className="zkp-badge">
            <span className="badge-dot"></span>
            ZKP Active: {zkpStatus.protocol} / {zkpStatus.hash}
          </div>
        )}
      </div>

      <div className="stepper">
        {["Identity", "Capture", "Proof", "Verify"].map((label, i) => (
          <div
            key={label}
            className={`step-item ${step >= i + 1 ? "active" : ""}`}
          >
            {i + 1}. {label}
          </div>
        ))}
      </div>

      <div className="zkp-card glass">
        {/* ── Step 1: Identity ── */}
        {step === 1 && (
          <div className="step-content animate-fade-in">
            <h3>Enter your Subject ID</h3>
            <p className="description">
              Provide the identity identifier you registered with.
            </p>
            <div className="input-group">
              <input
                type="text"
                placeholder="e.g. abc123def456..."
                value={subjectId}
                onChange={(e) => setSubjectId(e.target.value)}
              />
            </div>

            <h3>Biometric Type</h3>
            <div className="biometric-options">
              {["facial", "fingerprint", "iris"].map((type) => (
                <button
                  key={type}
                  className={`option-btn ${biometricType === type ? "selected" : ""}`}
                  onClick={() => setBiometricType(type)}
                >
                  <span>{getBiometricIcon(type)}</span>
                  {type.charAt(0).toUpperCase() + type.slice(1)}
                </button>
              ))}
            </div>

            {/* Eye side selector — iris only */}
            {isIris && (
              <div className="eye-side-section">
                <h3 style={{ fontSize: "1.1rem", marginBottom: "0.5rem" }}>
                  Which eye did you enroll?
                </h3>
                <div className="eye-side-row">
                  {["left", "right"].map((side) => (
                    <button
                      key={side}
                      className={`eye-btn ${eyeSide === side ? "eye-btn-active" : ""}`}
                      onClick={() => setEyeSide(side)}
                    >
                      👁️ {side.charAt(0).toUpperCase() + side.slice(1)} Eye
                      {eyeSide === side && " ✓"}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Fingerprint sensor note */}
            {isFingerprint && (
              <div className="sensor-note">
                ℹ️ Your power button sensor will be used — no webcam needed
              </div>
            )}

            <button
              className="btn-primary"
              disabled={!subjectId || subjectId.length < 8}
              onClick={() => setStep(2)}
            >
              Continue to Capture
            </button>
          </div>
        )}

        {/* ── Step 2: Capture ── */}
        {step === 2 && (
          <div className="step-content animate-fade-in">
            <h3>Biometric Capture</h3>

            {/* Fingerprint: sensor UI */}
            {isFingerprint ? (
              <>
                <p className="description">
                  Place your finger on the power button sensor to capture.
                </p>
                <div className="sensor-box">
                  <div
                    className={`sensor-ring-zkp ${isSensorCapturing ? "scanning" : ""}`}
                  >
                    <span className="sensor-icon-zkp">👆</span>
                    {isSensorCapturing && <div className="scan-line-zkp" />}
                  </div>
                  <p className="sensor-status">
                    {isSensorCapturing
                      ? "Scanning… Hold still"
                      : "Ready to scan"}
                  </p>
                </div>
                {error && <div className="zkp-error">{error}</div>}
                <button
                  className="btn-primary"
                  onClick={handleSensorCapture}
                  disabled={isSensorCapturing}
                >
                  {isSensorCapturing
                    ? "⏳ Scanning…"
                    : "👆 Scan & Generate ZKP"}
                </button>
              </>
            ) : (
              /* Face / Iris: webcam */
              <>
                <p className="description">
                  {isIris
                    ? `Align your ${eyeSide.toUpperCase()} eye with the oval. Your device will generate a cryptographic proof.`
                    : "Position your face within the frame. Your device will generate a cryptographic proof."}
                </p>
                {isIris && (
                  <div className="eye-reminder">
                    👁️ Using <strong>{eyeSide.toUpperCase()}</strong> eye
                    {eyeSide === "left"
                      ? " — tilt right side of face toward camera"
                      : " — tilt left side of face toward camera"}
                  </div>
                )}
                <div className="webcam-wrapper">
                  <Webcam
                    audio={false}
                    ref={webcamRef}
                    screenshotFormat="image/jpeg"
                    className="webcam-view"
                    videoConstraints={{ facingMode: "user" }}
                  />
                  <div className="webcam-overlay">
                    {isIris ? (
                      <div className={`iris-guide-zkp iris-guide-${eyeSide}`}>
                        <div className="iris-label-zkp">
                          {eyeSide.toUpperCase()} EYE
                        </div>
                      </div>
                    ) : (
                      <div className="facial-guide" />
                    )}
                  </div>
                </div>
                <button className="btn-primary" onClick={handleCapture}>
                  📸 Capture &amp; Generate ZKP
                </button>
              </>
            )}
          </div>
        )}

        {/* ── Step 3: Proof generation ── */}
        {step === 3 && (
          <div className="step-content animate-fade-in">
            <h3>Generating Zero-Knowledge Proof</h3>
            <p className="description">
              Computing Poseidon hash commitment and Groth16 proof…
            </p>
            <div className="progress-container">
              <div
                className="progress-bar"
                style={{ width: `${proofProgress}%` }}
              ></div>
            </div>
            <div className="status-text">{proofProgress}% Complete</div>
            <div className="proof-steps">
              {[
                [10, "Extracting biometric features…"],
                [30, "Quantizing to field elements…"],
                [50, "Computing Poseidon hash…"],
                [70, "Generating Groth16 proof…"],
                [90, "Verifying proof on-chain…"],
              ].map(([threshold, label]) => (
                <div
                  key={label}
                  className={`proof-step ${proofProgress > threshold ? "done" : ""}`}
                >
                  {label}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Step 4: Result ── */}
        {step === 4 && (
          <div className="step-content animate-fade-in">
            {!verificationResult ? (
              <div className="loading-spinner-container">
                <div className="spinner"></div>
                <p>Processing…</p>
              </div>
            ) : (
              <div
                className={`result-container ${verificationResult.success ? "success" : "failure"}`}
              >
                <div className="result-icon">
                  {verificationResult.success ? "✓" : "✗"}
                </div>
                <h2>
                  {verificationResult.success
                    ? "Identity Verified"
                    : "Verification Failed"}
                </h2>
                <p>{verificationResult.message}</p>

                {verificationResult.success && verificationResult.proof && (
                  <div className="proof-details glass">
                    <h4>ZKP Proof Details</h4>
                    <div className="detail-row">
                      <span>Protocol:</span>
                      <span>
                        {verificationResult.proof.protocol} (zk-SNARK)
                      </span>
                    </div>
                    <div className="detail-row">
                      <span>Curve:</span>
                      <span>{verificationResult.proof.curve || "bn128"}</span>
                    </div>
                    <div className="detail-row">
                      <span>Similarity:</span>
                      <span>
                        {(verificationResult.similarity * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="detail-row">
                      <span>Proof Valid:</span>
                      <span className="secure">
                        {verificationResult.proof.valid ? "YES" : "NO"}
                      </span>
                    </div>
                    {verificationResult.privacy && (
                      <>
                        <div className="detail-row">
                          <span>Biometric Revealed:</span>
                          <span className="secure">
                            {verificationResult.privacy.biometric_revealed
                              ? "YES"
                              : "NO (Private)"}
                          </span>
                        </div>
                        <div className="detail-row">
                          <span>Proof Size:</span>
                          <span>
                            {verificationResult.privacy.proof_size_bytes} bytes
                          </span>
                        </div>
                      </>
                    )}
                  </div>
                )}
                <button className="btn-secondary" onClick={reset}>
                  ↺ Try Again
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="zkp-info">
        <div className="info-card glass">
          <h4>Privacy Preserved</h4>
          <p>
            Your biometric data never leaves your device. Only a mathematical
            proof is sent to the server.
          </p>
        </div>
        <div className="info-card glass">
          <h4>Blockchain Verified</h4>
          <p>
            The proof is verified against the Poseidon hash commitment stored
            on-chain.
          </p>
        </div>
        <div className="info-card glass">
          <h4>Groth16 Protocol</h4>
          <p>
            Uses industry-standard zk-SNARK with bn128 elliptic curve for
            efficient verification.
          </p>
        </div>
      </div>
    </div>
  );
};

export default ZKPAuthentication;
