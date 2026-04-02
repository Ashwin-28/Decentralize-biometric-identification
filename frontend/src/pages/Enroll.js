import React, { useState, useRef, useCallback } from "react";
import Webcam from "react-webcam";
import {
  enrollSubject,
  checkLiveness,
  webauthnRegisterOptions,
  webauthnRegisterVerify,
} from "../services/api";
import { cropBiometricImage } from "../utils/imageCapture";
import "./Enroll.css";

function Enroll() {
  const webcamRef = useRef(null);
  const [step, setStep] = useState(1);
  const [name, setName] = useState("");
  const [biometricType, setBiometricType] = useState("facial");
  const [eyeSide] = useState("left");
  const [capturedImage, setCapturedImage] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSensorCapturing, setIsSensorCapturing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [sensorStatus, setSensorStatus] = useState("");
  const [fingerprintHash, setFingerprintHash] = useState(null); // Store enrolled template hash

  const isFingerprint = biometricType === "fingerprint";
  const isVoice = biometricType === "voice";

  // Voice recording state
  const [isRecording, setIsRecording] = useState(false);
  const [recorder, setRecorder] = useState(null);
  const [recordingTime, setRecordingTime] = useState(0);
  const timerRef = useRef(null);

  // Browser STT state
  const [spokenPassword, setSpokenPassword] = useState("");
  const recognitionRef = useRef(null);

  const base64UrlToUint8Array = (base64Url) => {
    const padded = `${base64Url}${"=".repeat((4 - (base64Url.length % 4)) % 4)}`
      .replace(/-/g, "+")
      .replace(/_/g, "/");
    const binary = window.atob(padded);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes;
  };

  const arrayBufferToBase64Url = (buffer) => {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    for (let i = 0; i < bytes.length; i += 1) {
      binary += String.fromCharCode(bytes[i]);
    }
    return window
      .btoa(binary)
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/g, "");
  };

  const ensureWebAuthn = () => {
    if (!window.isSecureContext) {
      throw new Error("Fingerprint on web requires HTTPS (or localhost).");
    }
    if (!window.PublicKeyCredential || !navigator.credentials) {
      throw new Error("This browser does not support WebAuthn credentials.");
    }
  };

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
        setStep(3);
      } catch (err) {
        setCapturedImage(imageSrc);
        setStep(3);
      }
    }
  }, [webcamRef, biometricType, eyeSide]);

  // Fingerprint: browser-native authenticator prompt (phone/laptop/external)
  const captureSensor = async () => {
    setIsSensorCapturing(true);
    setError(null);
    try {
      ensureWebAuthn();

      if (!name.trim()) {
        throw new Error(
          "Please enter your name before fingerprint enrollment.",
        );
      }

      setSensorStatus("Waiting for your device authenticator prompt...");
      const optionsPayload = await webauthnRegisterOptions(name.trim());
      const publicKey = optionsPayload?.publicKey;

      if (
        !optionsPayload?.token ||
        !publicKey?.challenge ||
        !publicKey?.user?.id
      ) {
        throw new Error(
          "Invalid WebAuthn registration options returned by backend.",
        );
      }

      const credential = await navigator.credentials.create({
        publicKey: {
          ...publicKey,
          challenge: base64UrlToUint8Array(publicKey.challenge),
          user: {
            ...publicKey.user,
            id: base64UrlToUint8Array(publicKey.user.id),
          },
        },
      });

      if (!credential) {
        throw new Error(
          "No fingerprint credential was returned by the device.",
        );
      }

      const credentialPayload = {
        id: credential.id,
        rawId: arrayBufferToBase64Url(credential.rawId),
        type: credential.type,
        response: {
          clientDataJSON: arrayBufferToBase64Url(
            credential.response.clientDataJSON,
          ),
          attestationObject: arrayBufferToBase64Url(
            credential.response.attestationObject,
          ),
        },
      };

      const verifyResult = await webauthnRegisterVerify(
        optionsPayload.token,
        name.trim(),
        credentialPayload,
      );

      setFingerprintHash(verifyResult?.credential_id || null);
      setSensorStatus(
        "✅ Fingerprint credential enrolled successfully on this device.",
      );
      setResult(verifyResult);
      setStep(4);
    } catch (err) {
      console.error("Enrollment sensor error:", err);
      const errMsg = err.message || "Could not reach sensor.";
      setSensorStatus("Fingerprint enrollment failed.");
      setError(errMsg);
      window.alert(`Scan Failed: ${errMsg}`);
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
        setAudioBlob(blob);
        setStep(3);

        // Stop all tracks
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.onerror = (event) => {
        console.error("MediaRecorder error:", event.error);
        setError("Recorder error: " + (event.error?.name || "Unknown error"));
        alert("Recorder error: " + (event.error?.name || "Unknown error"));
      };

      // Start recording with a timeslice to ensure dataavailable is fired
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

  const [, setAudioBlob] = useState(null);

  const retake = () => {
    setCapturedImage(null);
    setStep(2);
  };

  const handleEnroll = async () => {
    if (!capturedImage || !name) return;
    setIsProcessing(true);
    setError(null);
    try {
      const response = await fetch(capturedImage);
      const blob = await response.blob();
      let file;
      if (isVoice) {
        file = new File([blob], "biometric.wav", { type: "audio/wav" });
      } else {
        file = new File([blob], "biometric.jpg", { type: "image/jpeg" });
      }

      // Only run liveness for face/voice (not fingerprint sensor)
      if (!isFingerprint && !isVoice) {
        const liveness = await checkLiveness(file);
        if (!liveness.is_live) {
          setError(
            "Liveness check failed. Please ensure you are using a live capture.",
          );
          setIsProcessing(false);
          return;
        }
      }

      const enrollResult = await enrollSubject(
        file,
        name,
        biometricType,
        null, // eyeSide removed
        isFingerprint ? fingerprintHash : null,
        spokenPassword, // Pass the captured text if available
      );
      setResult(enrollResult);
      setStep(4);
    } catch (err) {
      setError(
        err.response?.data?.error || "Enrollment failed. Please try again.",
      );
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
    if (isFingerprint)
      return "Use your device authenticator prompt to register fingerprint";
    if (isVoice)
      return "Click record and say your SECRET PASSWORD clearly. This will be used for future verification.";
    return "Position your face inside the guide — look straight at the camera";
  };

  return (
    <div className="page enroll-page">
      <div className="container">
        <div className="page-header text-center">
          <span className="mono-label">Identity Registration</span>
          <h1>Biometric Enrollment</h1>
          <p className="text-muted">
            Register your biometric identity on the blockchain
          </p>
        </div>

        {/* Progress Steps */}
        <div className="progress-steps">
          {["Details", "Capture", "Confirm", "Complete"].map((label, i) => (
            <div
              key={label}
              className={`progress-step ${step >= i + 1 ? "active" : ""}`}
            >
              <span className="step-num">{i + 1}</span>
              <span>{label}</span>
            </div>
          ))}
        </div>

        <div className="enroll-content card">
          {/* ── Step 1: Details ── */}
          {step === 1 && (
            <div className="step-content">
              <h3>Enter Your Details</h3>
              <div className="form-group">
                <label className="label">Full Name</label>
                <input
                  type="text"
                  className="input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Enter your name"
                />
              </div>

              <div className="form-group">
                <label className="label">Biometric Type</label>
                <div className="biometric-options">
                  {["facial", "fingerprint", "voice"].map((type) => (
                    <button
                      key={type}
                      className={`option-btn ${biometricType === type ? "selected" : ""}`}
                      onClick={() => setBiometricType(type)}
                    >
                      <span className="option-icon">
                        {getBiometricIcon(type)}
                      </span>
                      {type.charAt(0).toUpperCase() + type.slice(1)}
                    </button>
                  ))}
                </div>
              </div>

              {/* Fingerprint info banner */}
              {isFingerprint && (
                <div className="sensor-info-banner">
                  <span className="sensor-info-icon">ℹ️</span>
                  <div>
                    <strong>Using Device Fingerprint Authenticator</strong>
                    <p>
                      Phone browsers use phone biometrics. Laptops use built-in
                      or external authenticators.
                    </p>
                  </div>
                </div>
              )}

              <button
                className="btn btn-primary"
                onClick={() => setStep(2)}
                disabled={!name}
              >
                Continue to Capture →
              </button>
            </div>
          )}

          {/* ── Step 2: Capture ── */}
          {step === 2 && (
            <div className="step-content">
              <h3>
                Capture Your{" "}
                {biometricType.charAt(0).toUpperCase() + biometricType.slice(1)}
              </h3>

              {/* Fingerprint: sensor UI */}
              {isFingerprint ? (
                <div className="sensor-capture-container">
                  <div className="sensor-visual">
                    <div
                      className={`sensor-ring ${isSensorCapturing ? "scanning" : ""}`}
                    >
                      <div className="sensor-icon">👆</div>
                      {isSensorCapturing && (
                        <div className="sensor-scan-line" />
                      )}
                    </div>

                    {(isSensorCapturing || sensorStatus) && (
                      <div className="instruction-bubble">{sensorStatus}</div>
                    )}
                  </div>

                  <div className="step-guide mt-md">
                    <p>
                      <strong>Step:</strong> Click the button, then touch your
                      device sensor when prompted by the browser.
                    </p>
                  </div>

                  {error && <div className="error-message">{error}</div>}

                  <div className="action-buttons centered">
                    <button
                      className="btn btn-primary"
                      onClick={captureSensor}
                      disabled={isSensorCapturing}
                    >
                      {isSensorCapturing
                        ? "⏳ Waiting for fingerprint prompt..."
                        : "👆 Register Fingerprint on This Device"}
                    </button>
                  </div>
                </div>
              ) : (
                /* Face / Voice: UI */
                <>
                  <p className="capture-instruction">
                    {getCaptureInstruction()}
                  </p>

                  {isVoice ? (
                    <div className="voice-capture-container">
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
                          : "Step 2: Say your unique voice password clearly"}
                      </div>
                      <div className="action-buttons centered">
                        {!isRecording ? (
                          <button
                            className="btn btn-primary"
                            onClick={startRecording}
                          >
                            ⏺ Start Recording
                          </button>
                        ) : (
                          <button
                            className="btn btn-ruby"
                            onClick={stopRecording}
                            disabled={recordingTime < 3}
                            title={
                              recordingTime < 3
                                ? `Speak for at least ${3 - recordingTime} more seconds`
                                : "Stop and save recording"
                            }
                          >
                            ⏹{" "}
                            {recordingTime < 3
                              ? `Speak... (${3 - recordingTime}s)`
                              : "Stop & Save"}
                          </button>
                        )}
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="webcam-container">
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
                      </div>

                      <div className="action-buttons centered">
                        <button className="btn btn-primary" onClick={capture}>
                          📸 Capture
                        </button>
                        <div className="upload-btn-wrapper">
                          <input
                            type="file"
                            accept="image/*"
                            id="file-upload"
                            style={{ display: "none" }}
                            onChange={(e) => {
                              const file = e.target.files[0];
                              if (file) {
                                const reader = new FileReader();
                                reader.onloadend = () => {
                                  setCapturedImage(reader.result);
                                  setStep(3);
                                };
                                reader.readAsDataURL(file);
                              }
                            }}
                          />
                          <button
                            className="btn btn-outline"
                            onClick={() =>
                              document.getElementById("file-upload").click()
                            }
                          >
                            Upload Image
                          </button>
                        </div>
                      </div>
                    </>
                  )}
                </>
              )}
            </div>
          )}

          {/* ── Step 3: Confirm ── */}
          {step === 3 && (
            <div className="step-content">
              <h3>Confirm Your Capture</h3>
              <div className="captured-preview">
                {isVoice ? (
                  <div className="voice-preview">
                    <div className="success-icon">🎤</div>
                    <div className="fp-preview-label">
                      Voice password recorded successfully
                    </div>
                    <audio
                      controls
                      src={capturedImage}
                      className="audio-preview"
                    />
                  </div>
                ) : isFingerprint ? (
                  <div className="fp-preview">
                    <img src={capturedImage} alt="Fingerprint" />
                    <div className="fp-preview-label">
                      Fingerprint captured from sensor
                    </div>
                  </div>
                ) : (
                  <img src={capturedImage} alt="Captured biometric" />
                )}
              </div>
              {error && <div className="error-message">{error}</div>}
              <div className="action-buttons">
                <button className="btn btn-outline" onClick={retake}>
                  ↺ Retake
                </button>
                <button
                  className="btn btn-primary"
                  onClick={handleEnroll}
                  disabled={isProcessing}
                >
                  {isProcessing ? "⏳ Processing…" : "🔗 Enroll on Blockchain"}
                </button>
              </div>
            </div>
          )}

          {/* ── Step 4: Complete ── */}
          {step === 4 && result && (
            <div className="step-content text-center">
              <div className="success-icon">✓</div>
              <h3>Enrollment Successful!</h3>
              <p className="text-muted">
                Your biometric identity has been registered
              </p>

              <div className="result-details card-glass">
                <div className="result-item">
                  <span className="result-label">Subject ID</span>
                  <span className="result-value mono">
                    {result.subject_id?.slice(0, 16)}…
                  </span>
                </div>
                <div className="result-item">
                  <span className="result-label">Biometric Type</span>
                  <span className="result-value">
                    {getBiometricIcon(result.biometric_type)}{" "}
                    {result.biometric_type}
                  </span>
                </div>

                {result.transaction_hash && (
                  <div className="result-item">
                    <span className="result-label">Transaction</span>
                    <span className="result-value mono">
                      {result.transaction_hash?.slice(0, 16)}…
                    </span>
                  </div>
                )}
              </div>

              <p className="important-note">
                ⚠️ Save your Subject ID — you'll need it for authentication
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default Enroll;
