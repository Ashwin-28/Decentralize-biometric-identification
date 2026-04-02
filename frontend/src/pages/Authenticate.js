import React, { useState, useRef, useCallback } from "react";
import Webcam from "react-webcam";
import {
  API_BASE,
  authenticateSubject,
  captureFingerprint,
} from "../services/api";
import { cropBiometricImage } from "../utils/imageCapture";
import "./Authenticate.css";

const API_FALLBACK =
  "https://biometric-backend-app.kindstone-7b8f6cd7.southeastasia.azurecontainerapps.io/api";

function Authenticate() {
  const webcamRef = useRef(null);
  const [subjectId, setSubjectId] = useState("");
  const [searchName, setSearchName] = useState("");
  const [biometricType, setBiometricType] = useState("facial");
  const [eyeSide] = useState("left");
  const [capturedImage, setCapturedImage] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSensorCapturing, setIsSensorCapturing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [sensorStatus, setSensorStatus] = useState("");
  const [fingerprintHash, setFingerprintHash] = useState(null); // Store captured fingerprint hash for verification

  // Voice lookup state
  const [isUserVerified, setIsUserVerified] = useState(false);
  const [verifyingUser, setVerifyingUser] = useState(false);

  const isFingerprint = biometricType === "fingerprint";
  const isVoice = biometricType === "voice";

  // Voice recording state
  const [isRecording, setIsRecording] = useState(false);
  const [recorder, setRecorder] = useState(null);
  const [recordingTime, setRecordingTime] = useState(0);
  const timerRef = useRef(null);

  // Browser STT state
  const [spokenPassword, setSpokenPassword] = useState("");
  const spokenPasswordRef = useRef("");
  const recognitionRef = useRef(null);

  // Reset verification state when switching biometric types
  React.useEffect(() => {
    setIsUserVerified(false);
    setSearchName("");
    setError(null);
    setResult(null);
    setCapturedImage(null);
  }, [biometricType]);

  const capture = useCallback(async () => {
    const imageSrc = webcamRef.current.getScreenshot();
    if (imageSrc) {
      try {
        const croppedImage = await cropBiometricImage(
          imageSrc,
          biometricType,
          eyeSide,
        );
        setCapturedImage(croppedImage);
      } catch (err) {
        setCapturedImage(imageSrc);
      }
    }
  }, [webcamRef, biometricType, eyeSide]);

  // Re-initialization function to reconnect to the native fingerprint driver/backend
  const reconnectSensor = async () => {
    setIsSensorCapturing(true);
    setSensorStatus("🔄 Reconnecting to biometric service...");
    setError(null);
    try {
      // Test backend health and sensor availability
      const response = await fetch(`${API_BASE}/fingerprint/status`);
      const status = await response.json();
      if (status.available) {
        setSensorStatus("✅ Service Reconnected. Sensor is ready.");
        window.alert("✅ Biometric Service Reconnected successfully!");
      } else {
        throw new Error("Sensor service responding but hardware not detected.");
      }
    } catch (err) {
      console.error("Reconnect failed:", err);
      setSensorStatus("❌ Reconnection failed. Please check backend.");
      setError("Reconnect failed: " + err.message);
    } finally {
      setIsSensorCapturing(false);
    }
  };

  const captureSensor = async () => {
    const controller = new AbortController();
    const { signal } = controller;

    setIsSensorCapturing(true);
    setError(null);
    setSensorStatus("Initializing sensor... Please wait 3-5 seconds.");

    // Give 3 to 5 seconds to make the sensor ready
    await new Promise((resolve) => setTimeout(resolve, 4000));

    // Callback validation check
    const onCaptureSuccess = (data) => {
      console.log("[DEBUG] Callback triggered with data:", !!data);
      if (typeof setCapturedImage !== "function") {
        console.error(
          '[FATAL] State setter "setCapturedImage" is not a function!',
        );
        return;
      }

      // Update captured image and hash
      setCapturedImage(`data:image/png;base64,${data.image_b64}`);
      if (data.hash) {
        setFingerprintHash(data.hash);
        console.log(
          "[AUTH] Fingerprint hash stored for verification:",
          data.hash.substring(0, 20) + "...",
        );
      }

      if (data.simulated) {
        setSensorStatus(
          "⚠️ Sensor unavailable — simulated fingerprint captured.",
        );
      } else {
        setSensorStatus("✅ Fingerprint scanned successfully!");
      }
    };

    const runCaptureWithRetry = async (retryCount = 0) => {
      const MAX_RETRIES = 2;
      setSensorStatus(
        "Sensor is ready. Please place your finger on the sensor.",
      );

      try {
        const TIMEOUT_MS = 25000;
        const timeoutId = setTimeout(() => {
          controller.abort();
        }, TIMEOUT_MS);

        const keepAlive = setInterval(() => {
          console.debug(
            `[HEARTBEAT] Biometric bridge active (Scan ${retryCount + 1})`,
          );
        }, 3000);

        try {
          const data = await captureFingerprint(signal);
          clearTimeout(timeoutId);
          clearInterval(keepAlive);

          if (data && data.success) {
            onCaptureSuccess(data);
          } else {
            throw new Error(data?.error || "Sensor capture failed.");
          }
        } catch (innerErr) {
          clearTimeout(timeoutId);
          clearInterval(keepAlive);
          if (innerErr.name === "AbortError") {
            throw new Error("Scan timed out. Please try again.");
          }
          throw innerErr;
        }
      } catch (err) {
        const isChannelClosed =
          err.message?.includes("message channel closed") ||
          err.message?.includes("Network Error") ||
          err.message?.includes("AxiosError");

        if (isChannelClosed && retryCount < MAX_RETRIES) {
          setSensorStatus(`Connection lost. Re-initializing...`);
          await new Promise((r) => setTimeout(r, 2000));
          return runCaptureWithRetry(retryCount + 1);
        }

        throw err;
      }
    };

    try {
      await runCaptureWithRetry();
    } catch (err) {
      console.error("[BRIDGE] Capture failure:", err);
      setError(err.message || "Could not reach sensor.");
      setSensorStatus("Scan failed.");
    } finally {
      setIsSensorCapturing(false);
    }
  };

  // ── Voice Recording Logic ──
  const startRecording = async () => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      const msg =
        "Audio recording is not supported in this browser or context (requires HTTPS or localhost).";
      setError(msg);
      alert(msg);
      return;
    }

    try {
      console.log("Requesting microphone access...");
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      console.log("Microphone access granted.");

      setSpokenPassword(""); // Reset transcript

      // Start Browser STT side-by-side
      if (
        "webkitSpeechRecognition" in window ||
        "SpeechRecognition" in window
      ) {
        try {
          const SpeechRecognition =
            window.SpeechRecognition || window.webkitSpeechRecognition;
          const recognition = new SpeechRecognition();
          recognition.continuous = true;
          recognition.interimResults = true;
          recognition.lang = "en-US";

          recognition.onresult = (event) => {
            const transcript = Array.from(event.results)
              .map((result) => result[0].transcript)
              .join(" ");
            setSpokenPassword(transcript);
            spokenPasswordRef.current = transcript;
            console.debug("[STT-DEBUG] Current transcript:", transcript);
          };

          recognition.onerror = (event) => {
            console.warn("[STT-WARN] Speech recognition error:", event.error);
          };

          recognition.start();
          recognitionRef.current = recognition;
        } catch (sttErr) {
          console.error(
            "[STT-ERR] Failed to start speech recognition:",
            sttErr,
          );
        }
      }

      // Determine supported MIME type
      const mimeType = MediaRecorder.isTypeSupported("audio/wav")
        ? "audio/wav"
        : "audio/webm";
      console.log(`Using MIME type: ${mimeType}`);

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      const chunks = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunks.push(e.data);
          console.debug("Received audio chunk, size:", e.data.size);
        }
      };

      mediaRecorder.onstop = () => {
        console.log("Recording stopped. Total chunks:", chunks.length);
        const blob = new Blob(chunks, { type: mimeType });
        const url = URL.createObjectURL(blob);
        setCapturedImage(url);

        // Stop all tracks
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.onerror = (event) => {
        console.error("MediaRecorder error:", event.error);
        setError("Recorder error: " + (event.error?.name || "Unknown error"));
        alert("Recorder error: " + (event.error?.name || "Unknown error"));
      };

      // Start recording with a timeslice
      mediaRecorder.start(200);
      setRecorder(mediaRecorder);
      setIsRecording(true);
      setRecordingTime(0);

      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = setInterval(() => {
        setRecordingTime((t) => t + 1);
      }, 1000);
      console.log("Recording started.");
    } catch (err) {
      console.error("Error starting recording:", err);
      let msg = "Could not access microphone.";
      if (err.name === "NotAllowedError") msg = "Microphone permission denied.";
      else if (err.name === "NotFoundError") msg = "No microphone detected.";
      setError(msg + " Please check your browser settings.");
      alert(msg);
    }
  };

  const stopRecording = () => {
    if (recorder && isRecording) {
      recorder.stop();
      setIsRecording(false);
      clearInterval(timerRef.current);

      // Stop STT
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (e) {}
      }
    }
  };

  const verifyUserByName = async () => {
    const trimmedName = searchName.trim();
    if (!trimmedName) {
      setError("Please enter your registered name or subject ID first");
      return;
    }

    // Never hard-block the user here. The backend authenticate API can still
    // resolve by subject id/name and return the final truth.
    const initialIdentifier = (subjectId || trimmedName).trim();
    setIsUserVerified(true);
    if (initialIdentifier) {
      setSubjectId(initialIdentifier);
    }
    setSensorStatus(
      "✅ Proceed to record. Identity will be validated on verify.",
    );

    setVerifyingUser(true);
    setError(null);
    try {
      const candidates = [
        `${API_BASE}/check-user`,
        `${API_FALLBACK}/check-user`,
      ];
      const endpoints = [...new Set(candidates)];
      let data = null;
      let lastError = null;

      for (const endpoint of endpoints) {
        try {
          const response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            cache: "no-store",
            body: JSON.stringify({ query: trimmedName }),
          });

          const rawText = await response.text();
          if (!response.ok) {
            const suffix = rawText ? `: ${rawText.slice(0, 160)}` : "";
            throw new Error(
              `Backend returned ${response.status} from ${endpoint}${suffix}`,
            );
          }

          let parsed;
          try {
            parsed = rawText ? JSON.parse(rawText) : {};
          } catch {
            throw new Error(`Unexpected response format from ${endpoint}`);
          }

          data = parsed;
          break;
        } catch (innerErr) {
          lastError = innerErr;
        }
      }

      if (!data) {
        throw lastError || new Error("Unable to reach backend");
      }

      if (data.exists) {
        setIsUserVerified(true);
        const sId = data.subject_id || subjectId;
        if (sId) {
          setSubjectId(sId);
        }
        setSensorStatus("✅ User found. Please record your password audio.");
      } else {
        // Keep flow open; backend will still validate on verify.
        setSensorStatus(
          "⚠ User not confirmed in lookup. You can still continue to verify.",
        );
      }
    } catch (err) {
      // Keep flow open even on lookup transport issues.
      setSensorStatus(
        `⚠ Lookup unavailable (${err.message || "Unknown"}). Continue to verify.`,
      );
    } finally {
      setVerifyingUser(false);
    }
  };

  const reset = () => {
    setCapturedImage(null);
    setIsUserVerified(false);
    setResult(null);
    setError(null);
  };

  const handleAuthenticate = async () => {
    if (!capturedImage || !subjectId) {
      window.alert("Please capture biometric and enter Subject ID first.");
      return;
    }

    setIsProcessing(true);
    setError(null);
    setResult(null);

    try {
      // 1. Convert captured image/audio to file
      const response = await fetch(capturedImage);
      const blob = await response.blob();
      let file;
      if (isVoice) {
        file = new File([blob], "biometric.wav", { type: "audio/wav" });
      } else if (isFingerprint) {
        file = new File([blob], "biometric.jpg", { type: "image/jpeg" });
      } else {
        file = new File([blob], "biometric.jpg", { type: "image/jpeg" });
      }

      // Debug: Log what password we're sending
      const passwordToSend = spokenPasswordRef.current || spokenPassword;
      console.log("[AUTH] Sending spoken password:", passwordToSend);
      console.log("[AUTH] spokenPassword state:", spokenPassword);
      console.log("[AUTH] spokenPasswordRef:", spokenPasswordRef.current);

      // 2. Perform authentication with the backend
      const authResult = await authenticateSubject(
        file,
        subjectId,
        biometricType,
        null, // eyeSide removed
        isFingerprint ? fingerprintHash : null,
        spokenPasswordRef.current || spokenPassword, // Use ref for latest STT value
      );

      if (authResult.success) {
        authResult.ui_message = "✅ MATCHED SUCCESSFUL";
      } else {
        authResult.ui_message = "❌ NOT MATCHED";
      }

      setResult(authResult);
    } catch (err) {
      console.error("Auth Error:", err);
      const errMsg =
        err.response?.data?.error || "Verification encountered an error.";
      setError(errMsg);
      setResult({ success: false, ui_message: "❌ NOT MATCHED" });
    } finally {
      setIsProcessing(false);
    }
  };

  const getBiometricIcon = (type) => {
    if (type === "facial") return "👤";
    if (type === "fingerprint") return "👆";
    if (type === "voice") return "🎤";
    return "🔍";
  };

  const getCaptureInstruction = () => {
    if (isVoice) return "Click record and say your password";
    return "Position your face inside the guide — look straight at camera";
  };

  return (
    <div className="page auth-page">
      <div className="container">
        <div className="page-header text-center">
          <span className="mono-label">Identity Verification</span>
          <h1>Authenticate</h1>
          <p className="text-muted">
            Verify your identity against the blockchain record
          </p>
        </div>

        <div className="auth-layout">
          {/* ── Input Section ── */}
          <div className="auth-input card">
            <h3>Subject ID</h3>
            <input
              type="text"
              className="input"
              value={subjectId}
              onChange={(e) => setSubjectId(e.target.value)}
              placeholder="Enter your subject ID"
            />

            <div className="gold-line"></div>

            <h3>Biometric Type</h3>
            <div className="biometric-options">
              {["facial", "fingerprint", "voice"].map((type) => (
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

            <div className="gold-line"></div>
            <h3>Biometric Capture</h3>

            {/* Fingerprint: sensor */}
            {isFingerprint && !capturedImage && (
              <div className="sensor-capture-container">
                <div className="sensor-visual">
                  <div
                    className={`sensor-ring ${isSensorCapturing ? "scanning" : ""}`}
                  >
                    <div className="sensor-icon">👆</div>
                    {isSensorCapturing && <div className="sensor-scan-line" />}
                  </div>
                  <p className="sensor-label">
                    {isSensorCapturing
                      ? sensorStatus || "Scanning… Hold still"
                      : "Ready (Touch sensor)"}
                  </p>
                </div>
                {error && <div className="error-message">{error}</div>}
                <div className="action-buttons centered">
                  <button
                    className="btn btn-primary"
                    onClick={captureSensor}
                    disabled={isSensorCapturing}
                  >
                    {isSensorCapturing ? "⏳ Scanning…" : "👆 SCAN FINGERPRINT"}
                  </button>
                  <button
                    className="btn btn-outline"
                    onClick={reconnectSensor}
                    disabled={isSensorCapturing}
                  >
                    {isSensorCapturing ? "⏳ Resetting..." : "🔄 RECONNECT"}
                  </button>
                </div>
                <div className="step-guide mt-md">
                  <p>
                    <strong>Step 1:</strong> Place finger on sensor and click
                    scan
                  </p>
                </div>
              </div>
            )}

            {/* Face / Voice: UI */}
            {!isFingerprint && !capturedImage && (
              <div className="webcam-container">
                <p className="capture-instruction">{getCaptureInstruction()}</p>

                {isVoice ? (
                  <div className="voice-capture-container">
                    {!isUserVerified ? (
                      <div className="voice-lookup-step">
                        <p className="capture-instruction">
                          Step 1: Verify your identity in the system
                        </p>
                        <input
                          type="text"
                          className="input mb-md"
                          value={searchName}
                          onChange={(e) => setSearchName(e.target.value)}
                          placeholder="Type your registered name or subject ID"
                          autoComplete="off"
                        />
                        <button
                          className="btn btn-primary"
                          onClick={verifyUserByName}
                          disabled={verifyingUser || !searchName}
                        >
                          {verifyingUser ? "⏳ Checking..." : "🔍 Search User"}
                        </button>
                      </div>
                    ) : (
                      <>
                        <div
                          className={`voice-visualizer ${isRecording ? "active" : ""}`}
                        >
                          {isRecording ? (
                            <div className="recording-wave">
                              <span></span>
                              <span></span>
                              <span></span>
                              <span></span>
                              <span></span>
                            </div>
                          ) : (
                            <div className="mic-placeholder">🎤</div>
                          )}
                        </div>
                        <div className="recording-timer">
                          {isRecording
                            ? `Recording: ${recordingTime}s`
                            : "Step 2: Say your SECRET PASSWORD clearly"}
                        </div>

                        <div className="challenge-display card-glass mb-md">
                          <span className="mono-label">
                            Voice Password Verification
                          </span>
                          <div
                            className="challenge-code"
                            style={{ fontSize: "1.2rem" }}
                          >
                            🔐 Speak Your Enrollment Password
                          </div>
                          <p className="text-muted small">
                            Say the same password you used during registration
                          </p>
                        </div>

                        <div className="action-buttons centered">
                          {!isRecording ? (
                            <button
                              className="btn btn-primary"
                              onClick={startRecording}
                            >
                              ⏺ Record Password
                            </button>
                          ) : (
                            <button
                              className="btn btn-ruby"
                              onClick={stopRecording}
                              disabled={recordingTime < 2}
                              title={
                                recordingTime < 2
                                  ? "Speak for at least 2 more seconds"
                                  : "Stop recording"
                              }
                            >
                              ⏹{" "}
                              {recordingTime < 2
                                ? `Speak... (${2 - recordingTime}s)`
                                : "Stop & Save"}
                            </button>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                ) : (
                  <>
                    <Webcam
                      ref={webcamRef}
                      audio={false}
                      screenshotFormat="image/jpeg"
                      videoConstraints={{ facingMode: "user" }}
                      className="webcam"
                    />
                    <div className="webcam-overlay">
                      <div className="facial-guide" />
                    </div>

                    <div className="action-buttons centered mt-lg">
                      <button className="btn btn-primary" onClick={capture}>
                        📸 Capture
                      </button>
                      <div className="upload-btn-wrapper">
                        <input
                          type="file"
                          accept="image/*"
                          id="auth-file-upload"
                          style={{ display: "none" }}
                          onChange={(e) => {
                            const file = e.target.files[0];
                            if (file) {
                              const reader = new FileReader();
                              reader.onloadend = () =>
                                setCapturedImage(reader.result);
                              reader.readAsDataURL(file);
                            }
                          }}
                        />
                        <button
                          className="btn btn-outline"
                          onClick={() =>
                            document.getElementById("auth-file-upload").click()
                          }
                        >
                          Upload
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}

            {/* Captured state */}
            {capturedImage && (
              <div className="captured-container">
                {isVoice ? (
                  <div className="voice-preview">
                    <div className="success-icon">🎤</div>
                    <audio
                      controls
                      src={capturedImage}
                      className="audio-preview"
                    />
                  </div>
                ) : (
                  <div className="fingerprint-preview-container">
                    <img
                      src={capturedImage}
                      alt="Captured"
                      className="captured-img"
                    />
                    {isFingerprint && (
                      <div className="step-guide mt-md">
                        <p className="text-emerald">
                          <strong>Step 2:</strong> Fingerprint captured. Click
                          VERIFY to continue.
                        </p>
                      </div>
                    )}
                  </div>
                )}
                <div className="capture-actions">
                  <button className="btn btn-outline" onClick={reset}>
                    ↺ Retake
                  </button>
                  <button
                    className="btn btn-primary"
                    id="verify-button"
                    onClick={handleAuthenticate}
                    disabled={!subjectId || isProcessing}
                  >
                    {isProcessing ? "⏳ Verifying…" : "🔍 VERIFY IDENTITY"}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* ── Result Section ── */}
          <div className="auth-result card">
            <h3>Verification Result</h3>

            {!result && !error && (
              <div className="result-placeholder">
                <div className="placeholder-icon">🔍</div>
                <p>Capture your biometric and click verify to see results</p>
              </div>
            )}

            {error && (
              <div className="result-error">
                <div className="result-icon error">✕</div>
                <h4>Verification Failed</h4>
                <p>{error}</p>
              </div>
            )}

            {result && !error && (
              <div
                className={`result-display ${result.success ? "success" : "failure"}`}
              >
                <div
                  className={`result-icon ${result.success ? "success" : "error"}`}
                >
                  {result.success ? "✓" : "✕"}
                </div>
                <h4>
                  {result.success
                    ? "Verification Successful"
                    : "Verification Failed"}
                </h4>
                <p
                  style={{
                    fontSize: "1.2rem",
                    fontWeight: "bold",
                    color: result.success
                      ? "var(--accent-emerald)"
                      : "var(--accent-ruby)",
                    margin: "1rem 0",
                  }}
                >
                  {result.ui_message}
                </p>
                <p>
                  {result.message ||
                    (result.success
                      ? "Your identity has been verified successfully."
                      : "Biometric verification failed. Please try again.")}
                </p>

                {result.confidence !== undefined && (
                  <div className="confidence-score">
                    <span className="confidence-label">Confidence:</span>
                    <span
                      className={`confidence-value ${result.confidence >= 70 ? "high" : "low"}`}
                    >
                      {result.confidence.toFixed(2)}%
                    </span>
                  </div>
                )}

                <div className="result-meta">
                  <div className="meta-item">
                    <span className="meta-label">Subject ID</span>
                    <span className="meta-value">
                      {result.subject_id?.slice(0, 16)}…
                    </span>
                  </div>
                  {result.logged_on_chain !== undefined && (
                    <div className="meta-item">
                      <span className="meta-label">Logged on Chain</span>
                      <span className="meta-value">
                        {result.logged_on_chain ? "Yes" : "No"}
                      </span>
                    </div>
                  )}
                </div>

                {result.hashes && (
                  <div className="result-meta" style={{ marginTop: "1rem" }}>
                    <div
                      style={{
                        marginBottom: "0.5rem",
                        fontSize: "0.85rem",
                        color: "var(--text-muted)",
                        textTransform: "uppercase",
                        letterSpacing: "1px",
                      }}
                    >
                      Cryptographic Proof
                    </div>
                    <div className="meta-item">
                      <span className="meta-label">Stored Hash</span>
                      <span className="meta-value" title={result.hashes.stored}>
                        {result.hashes.stored
                          ? result.hashes.stored.slice(0, 10) +
                            "…" +
                            result.hashes.stored.slice(-8)
                          : "---"}
                      </span>
                    </div>
                    <div className="meta-item">
                      <span className="meta-label">Computed Hash</span>
                      <span className="meta-value">
                        {result.hashes.computed
                          ? result.hashes.computed.slice(0, 10) +
                            "…" +
                            result.hashes.computed.slice(-8)
                          : "---"}
                      </span>
                    </div>
                    <div className="meta-item">
                      <span className="meta-label">Match Score</span>
                      <span
                        className="meta-value"
                        style={{ fontWeight: "bold" }}
                      >
                        {result.confidence
                          ? Number(result.confidence).toFixed(2) + "%"
                          : "N/A"}
                      </span>
                    </div>
                    <div className="meta-item">
                      <span className="meta-label">Integrity Status</span>
                      <span
                        className="meta-value"
                        style={{
                          color: result.hashes.match
                            ? "var(--accent-emerald)"
                            : "var(--accent-ruby)",
                          fontWeight: "bold",
                        }}
                      >
                        {result.hashes.match ? "✓ VERIFIED" : "✕ FAILED"}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Authenticate;
