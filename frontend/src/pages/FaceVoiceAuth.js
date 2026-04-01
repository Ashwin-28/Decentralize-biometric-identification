import React, { useState, useRef, useCallback } from 'react';
import Webcam from 'react-webcam';
import { cropBiometricImage } from '../utils/imageCapture';
import { multimodalEnroll, multimodalAuthenticate } from '../services/api';
import "./FaceVoiceAuth.css";

// ─── helpers ────────────────────────────────────────────────────────────────

const b64ToFile = async (b64, name) => {
    const res = await fetch(b64);
    const blob = await res.blob();
    const type = name.endsWith('.wav') ? 'audio/wav' : 'image/jpeg';
    return new File([blob], name, { type });
};

// ─── sub-component: capture modal ───────────────────────────────────────────

const CaptureModal = ({ mode, onCapture, onCancel }) => {
    const webcamRef = useRef(null);
    const [ready, setReady] = useState(false);
    const [isRecording, setIsRecording] = useState(false);
    const [recorder, setRecorder] = useState(null);
    const [recordingTime, setRecordingTime] = useState(0);
    const timerRef = useRef(null);

    const shoot = useCallback(async () => {
        const raw = webcamRef.current?.getScreenshot();
        if (!raw) return;
        try {
            const cropped = await cropBiometricImage(raw, 'facial');
            onCapture(cropped);
        } catch {
            onCapture(raw);
        }
    }, [onCapture]);

    const startRecording = async () => {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            console.error('Recording not supported');
            alert('Audio recording is not supported in this browser or context (requires HTTPS or localhost).');
            return;
        }

        try {
            console.log('Requesting microphone access...');
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            console.log('Microphone access granted.');
            
            // Determine supported MIME type
            const mimeType = MediaRecorder.isTypeSupported('audio/wav') ? 'audio/wav' : 'audio/webm';
            console.log(`Using MIME type: ${mimeType}`);
            
            const mediaRecorder = new MediaRecorder(stream, { mimeType });
            const chunks = [];
            
            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    chunks.push(e.data);
                    console.debug('Received audio chunk, size:', e.data.size);
                }
            };
            
            mediaRecorder.onstop = () => {
                console.log('Recording stopped. Total chunks:', chunks.length);
                const blob = new Blob(chunks, { type: mimeType });
                const url = URL.createObjectURL(blob);
                onCapture(url);
                stream.getTracks().forEach(track => track.stop());
            };
            
            mediaRecorder.onerror = (e) => {
                console.error('Recorder error:', e);
                alert('Recorder error: ' + e.message);
            };

            mediaRecorder.start(200); // Smaller timeslice for better reliability
            setRecorder(mediaRecorder);
            setIsRecording(true);
            setRecordingTime(0);
            if (timerRef.current) clearInterval(timerRef.current);
            timerRef.current = setInterval(() => setRecordingTime(t => t + 1), 1000);
            console.log('Recording started.');
        } catch (err) {
            console.error('Mic error:', err);
            alert('Microphone error: ' + err.message);
        }
    };

    const stopRecording = () => {
        if (recorder) {
            recorder.stop();
            setIsRecording(false);
            clearInterval(timerRef.current);
        }
    };

    return (
        <div className="fi-overlay">
            <div className="fi-modal glass-dark">
                <div className="fi-modal-header">
                    <span className="fi-modal-icon">{mode === 'face' ? '👤' : '🎤'}</span>
                    <h2>Capture {mode === 'face' ? 'Face' : 'Voice'}</h2>
                    <p className="fi-modal-hint">
                        {mode === 'face'
                            ? 'Look straight at the camera. Keep your face centred.'
                            : 'Click record and say your secret password clearly.'}
                    </p>
                </div>

                <div className="fi-viewport">
                    {mode === 'face' ? (
                        <>
                            <Webcam
                                ref={webcamRef}
                                audio={false}
                                screenshotFormat="image/jpeg"
                                videoConstraints={{ facingMode: 'user', width: 640, height: 480 }}
                                className="fi-webcam"
                                onUserMedia={() => setReady(true)}
                            />
                            <div className="fi-guide fi-guide-face" />
                            {!ready && <div className="fi-loading-cam">Initialising camera…</div>}
                        </>
                    ) : (
                        <div className="fi-voice-viewport">
                            <div className={`fi-voice-viz ${isRecording ? 'active' : ''}`}>
                                {isRecording ? '⏺ Recording' : '🎤 Ready'}
                            </div>
                            <div className="fi-voice-timer">{recordingTime}s</div>
                        </div>
                    )}
                </div>

                <div className="fi-modal-actions">
                    <button className="fi-btn fi-btn-ghost" onClick={onCancel}>Cancel</button>
                    {mode === 'face' ? (
                        <button className="fi-btn fi-btn-primary" onClick={shoot} disabled={!ready}>
                            📸 Capture
                        </button>
                    ) : !isRecording ? (
                        <button className="fi-btn fi-btn-primary" onClick={startRecording}>
                            ⏺ Start
                        </button>
                    ) : (
                        <button className="fi-btn fi-btn-ruby" onClick={stopRecording}>
                            ⏹ Stop
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};

// ─── sub-component: capture card ────────────────────────────────────────────

const CaptureCard = ({ label, icon, image, onCapture, onRetake, hint, type }) => (
    <div className={`fi-capture-card ${image ? 'fi-captured' : ''}`}>
        <div className="fi-capture-card-header">
            <span className="fi-capture-icon">{icon}</span>
            <div>
                <div className="fi-capture-label">{label}</div>
                <div className="fi-capture-hint">{hint}</div>
            </div>
            {image && <span className="fi-check">✓</span>}
        </div>

        {image ? (
            <div className="fi-preview-wrap">
                {type === 'voice' ? (
                    <audio src={image} controls className="fi-audio-preview" />
                ) : (
                    <img src={image} alt={label} className="fi-preview" />
                )}
                <button className="fi-retake-btn" onClick={onRetake}>↺ Retake</button>
            </div>
        ) : (
            <button className="fi-btn fi-btn-outline fi-full" onClick={onCapture}>
                Start Capture
            </button>
        )}
    </div>
);

// ─── sub-component: fusion result ───────────────────────────────────────────

const FusionResult = ({ result, onReset }) => {
    const { success, confidence, modalities, fusion_score, subject_id, subject_code, transaction_hash } = result;
    const pct = Math.min(100, Math.max(0, confidence ?? fusion_score * 100));

    const circumference = 2 * Math.PI * 54;
    const offset = circumference - (circumference * pct) / 100;

    return (
        <div className={`fi-result ${success ? 'fi-result-success' : 'fi-result-fail'}`}>
            <div className="fi-result-header">
                <div className="fi-result-badge">{success ? '✓' : '✗'}</div>
                <h2>{success ? 'Identity Verified' : 'Verification Failed'}</h2>
                <p className="fi-result-sub">
                    {success ? 'Multimodal biometric fusion passed' : 'One or more modalities did not match'}
                </p>
            </div>

            {/* Fusion score ring */}
            <div className="fi-score-ring-wrap">
                <svg className="fi-score-ring" viewBox="0 0 120 120">
                    <circle cx="60" cy="60" r="54" className="fi-ring-bg" />
                    <circle
                        cx="60" cy="60" r="54"
                        className={`fi-ring-fg ${success ? 'fi-ring-success' : 'fi-ring-fail'}`}
                        strokeDasharray={circumference}
                        strokeDashoffset={offset}
                    />
                </svg>
                <div className="fi-score-label">
                    <span className="fi-score-num">{pct.toFixed(1)}</span>
                    <span className="fi-score-unit">%</span>
                </div>
            </div>

            {/* Per-modality breakdown */}
            {modalities && (
                <div className="fi-breakdown">
                    {[
                        { key: 'face', icon: '👤', label: 'Face Recognition' },
                        { key: 'voice', icon: '🎤', label: 'Voice Analysis' },
                    ].map(({ key, icon, label }) => {
                        const m = modalities[key];
                        if (!m) return null;
                        return (
                            <div key={key} className="fi-breakdown-row">
                                <span className="fi-bd-icon">{icon}</span>
                                <span className="fi-bd-label">{label}</span>
                                <div className="fi-bd-bar">
                                    <div
                                        className={`fi-bd-fill ${m.passed ? 'fi-bd-pass' : 'fi-bd-fail'}`}
                                        style={{ width: `${m.confidence_pct ?? 0}%` }}
                                    />
                                </div>
                                <span className="fi-bd-pct">{(m.confidence_pct ?? 0).toFixed(1)}%</span>
                                <span className={`fi-bd-status ${m.passed ? 'pass' : 'fail'}`}>
                                    {m.passed ? '✓' : '✗'}
                                </span>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Subject info */}
            {(subject_id || subject_code || transaction_hash) && (
                <div className="fi-info-grid">
                    {subject_code && (
                        <div className="fi-info-item">
                            <span className="fi-info-label">Subject Code</span>
                            <span className="fi-info-value mono">{subject_code}</span>
                        </div>
                    )}
                    {subject_id && (
                        <div className="fi-info-item">
                            <span className="fi-info-label">Subject ID</span>
                            <span className="fi-info-value mono">{subject_id.slice(0, 20)}…</span>
                        </div>
                    )}
                    {transaction_hash && (
                        <div className="fi-info-item">
                            <span className="fi-info-label">Blockchain TX</span>
                            <span className="fi-info-value mono">{transaction_hash.slice(0, 20)}…</span>
                        </div>
                    )}
                </div>
            )}

            <button className="fi-btn fi-btn-ghost fi-full" onClick={onReset}>
                ↺ New Session
            </button>
        </div>
    );
};

// ─── main component ──────────────────────────────────────────────────────────

const TABS = ['enroll', 'authenticate'];

export default function FaceVoiceAuth() {
    const [tab, setTab] = useState('enroll');

    const [capturing, setCapturing] = useState(null);   // 'face' | 'voice' | null
    const [captureTarget, setCaptureTarget] = useState(null); // which slot is being filled

    // Enroll state
    const [enrollName, setEnrollName] = useState('');
    const [enrollFace, setEnrollFace] = useState(null);
    const [enrollVoice, setEnrollVoice] = useState(null);
    const [enrolling, setEnrolling] = useState(false);
    const [enrollResult, setEnrollResult] = useState(null);
    const [enrollError, setEnrollError] = useState(null);

    // Auth state
    const [authId, setAuthId] = useState('');
    const [authFace, setAuthFace] = useState(null);
    const [authVoice, setAuthVoice] = useState(null);
    const [authing, setAuthing] = useState(false);
    const [authResult, setAuthResult] = useState(null);
    const [authError, setAuthError] = useState(null);

    // ── capture flow ────────────────────────────────────────────────────────

    const openCapture = (slot, mode) => {
        setCaptureTarget(slot);
        setCapturing(mode);
    };

    const handleCapture = (data) => {
        if (captureTarget === 'enroll-face') setEnrollFace(data);
        else if (captureTarget === 'enroll-voice') setEnrollVoice(data);
        else if (captureTarget === 'auth-face') setAuthFace(data);
        else if (captureTarget === 'auth-voice') setAuthVoice(data);
        setCapturing(null);
        setCaptureTarget(null);
    };

    // ── enroll ───────────────────────────────────────────────────────────────

    const handleEnroll = async () => {
        if (!enrollFace || !enrollVoice || !enrollName.trim()) return;
        setEnrolling(true);
        setEnrollError(null);
        setEnrollResult(null);
        try {
            const faceFile = await b64ToFile(enrollFace, 'face.jpg');
            const voiceFile = await b64ToFile(enrollVoice, 'voice.wav');
            const res = await multimodalEnroll(faceFile, voiceFile, enrollName.trim(), 'multimodal_face_voice');
            setEnrollResult(res);
        } catch (err) {
            setEnrollError(err.response?.data?.error || err.message || 'Enrollment failed');
        } finally {
            setEnrolling(false);
        }
    };

    const resetEnroll = () => {
        setEnrollFace(null); setEnrollVoice(null);
        setEnrollName(''); setEnrollResult(null); setEnrollError(null);
    };

    // ── authenticate ─────────────────────────────────────────────────────────

    const handleAuth = async () => {
        if (!authFace || !authVoice || !authId.trim()) return;
        setAuthing(true);
        setAuthError(null);
        setAuthResult(null);
        try {
            const faceFile = await b64ToFile(authFace, 'face.jpg');
            const voiceFile = await b64ToFile(authVoice, 'voice.wav');
            const res = await multimodalAuthenticate(faceFile, voiceFile, authId.trim(), 'multimodal_face_voice');
            setAuthResult(res);
        } catch (err) {
            const msg = err.response?.data?.error || err.message || 'Authentication failed';
            setAuthError(msg);
        } finally {
            setAuthing(false);
        }
    };

    const resetAuth = () => {
        setAuthFace(null); setAuthVoice(null);
        setAuthId(''); setAuthResult(null); setAuthError(null);
    };

    // ── render ───────────────────────────────────────────────────────────────

    return (
        <div className="fi-page">
            {/* hero */}
            <div className="fi-hero">
                <div className="fi-hero-badge">MULTIMODAL BIOMETRICS</div>
                <h1 className="fi-hero-title">
                    Face <span className="fi-plus">+</span> Voice
                    <br />Authentication
                </h1>
                <p className="fi-hero-sub">
                    Dual-layer identity verification combining facial recognition (60%) and voice analysis (40%)
                    for maximum security and spoof resistance.
                </p>

                {/* weight pills */}
                <div className="fi-weight-pills">
                    <div className="fi-pill">
                        <span className="fi-pill-icon">👤</span>
                        <span className="fi-pill-label">Face</span>
                        <span className="fi-pill-weight">60%</span>
                    </div>
                    <div className="fi-pill-sep">⊕</div>
                    <div className="fi-pill">
                        <span className="fi-pill-icon">🎤</span>
                        <span className="fi-pill-label">Voice</span>
                        <span className="fi-pill-weight">40%</span>
                    </div>
                    <div className="fi-pill-sep">=</div>
                    <div className="fi-pill fi-pill-fusion">
                        <span className="fi-pill-icon">🔒</span>
                        <span className="fi-pill-label">Fusion</span>
                        <span className="fi-pill-weight">100%</span>
                    </div>
                </div>
            </div>

            {/* tab bar */}
            <div className="fi-tabs">
                {TABS.map(t => (
                    <button
                        key={t}
                        className={`fi-tab ${tab === t ? 'fi-tab-active' : ''}`}
                        onClick={() => setTab(t)}
                    >
                        {t === 'enroll' ? '📋 Enroll Identity' : '🔐 Authenticate'}
                    </button>
                ))}
            </div>

            {/* ── ENROLL TAB ─────────────────────────────────────────────────── */}
            {tab === 'enroll' && (
                <div className="fi-panel">
                    {enrollResult ? (
                        <FusionResult result={enrollResult} onReset={resetEnroll} />
                    ) : (
                        <>
                            <div className="fi-section-title">Step 1 — Enter Your Name</div>
                            <input
                                className="fi-input"
                                placeholder="Full name"
                                value={enrollName}
                                onChange={e => setEnrollName(e.target.value)}
                            />



                            <div className="fi-capture-grid">
                                <CaptureCard
                                    label="Face"
                                    icon="👤"
                                    type="face"
                                    image={enrollFace}
                                    hint="DeepFace / FaceNet512 · 512-D embedding"
                                    onCapture={() => openCapture('enroll-face', 'face')}
                                    onRetake={() => setEnrollFace(null)}
                                />
                                <CaptureCard
                                    label="Voice"
                                    icon="🎤"
                                    type="voice"
                                    image={enrollVoice}
                                    hint="Speech-to-Text · Password Matching"
                                    onCapture={() => openCapture('enroll-voice', 'voice')}
                                    onRetake={() => setEnrollVoice(null)}
                                />
                            </div>

                            {enrollError && <div className="fi-error">{enrollError}</div>}

                            <button
                                className="fi-btn fi-btn-primary fi-full fi-enroll-btn"
                                disabled={!enrollFace || !enrollVoice || !enrollName.trim() || enrolling}
                                onClick={handleEnroll}
                            >
                                {enrolling ? (
                                    <><span className="fi-spinner" /> Processing…</>
                                ) : (
                                    '🔗 Enroll on Blockchain'
                                )}
                            </button>

                            <p className="fi-note">
                                Both face and voice must be captured before enrollment. Your biometric templates are
                                encrypted and stored securely — only cryptographic commitments are written to the blockchain.
                            </p>
                        </>
                    )}
                </div>
            )}

            {/* ── AUTH TAB ───────────────────────────────────────────────────── */}
            {tab === 'authenticate' && (
                <div className="fi-panel">
                    {authResult ? (
                        <FusionResult result={authResult} onReset={resetAuth} />
                    ) : (
                        <>
                            <div className="fi-section-title">Step 1 — Enter Subject ID</div>
                            <input
                                className="fi-input"
                                placeholder="Paste your Subject ID (hex)"
                                value={authId}
                                onChange={e => setAuthId(e.target.value)}
                            />



                            <div className="fi-capture-grid">
                                <CaptureCard
                                    label="Face"
                                    icon="👤"
                                    type="face"
                                    image={authFace}
                                    hint="Must match enrolled face"
                                    onCapture={() => openCapture('auth-face', 'face')}
                                    onRetake={() => setAuthFace(null)}
                                />
                                <CaptureCard
                                    label="Voice"
                                    icon="🎤"
                                    type="voice"
                                    image={authVoice}
                                    hint="Must match enrolled password"
                                    onCapture={() => openCapture('auth-voice', 'voice')}
                                    onRetake={() => setAuthVoice(null)}
                                />
                            </div>

                            {authError && <div className="fi-error">{authError}</div>}

                            <button
                                className="fi-btn fi-btn-primary fi-full fi-enroll-btn"
                                disabled={!authFace || !authVoice || !authId.trim() || authing}
                                onClick={handleAuth}
                            >
                                {authing ? (
                                    <><span className="fi-spinner" /> Verifying…</>
                                ) : (
                                    '🔍 Verify Identity'
                                )}
                            </button>

                            <p className="fi-note">
                                Both modalities are verified independently. Authentication succeeds only when
                                face similarity ≥ 75%, voice similarity ≥ 50%, and the weighted fusion score ≥ 50%.
                            </p>
                        </>
                    )}
                </div>
            )}

            {/* capture modal */}
            {capturing && (
                <CaptureModal
                    mode={capturing}
                    onCapture={handleCapture}
                    onCancel={() => { setCapturing(null); setCaptureTarget(null); }}
                />
            )}
        </div>
    );
}
