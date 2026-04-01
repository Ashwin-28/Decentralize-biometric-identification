import React, { useState, useRef } from 'react';
import Webcam from 'react-webcam';
import { cropBiometricImage } from '../utils/imageCapture';
import './MultimodalAuth.css';

const MultimodalAuth = () => {
    const [selectedModalities, setSelectedModalities] = useState(['face', 'fingerprint']);
    const [currentCapturing, setCurrentCapturing] = useState(null);
    const [capturedData, setCapturedData] = useState({});
    const [isAuthenticating, setIsAuthenticating] = useState(false);
    const [fusionScore, setFusionScore] = useState(null);
    const [subjectId, setSubjectId] = useState('');

    const webcamRef = useRef(null);

    const modalities = [
        { id: 'face', name: 'Face', icon: '👤', weight: 0.45, description: '3D Mesh Analysis' },
        { id: 'fingerprint', name: 'Fingerprint', icon: '👆', weight: 0.35, description: 'Minutiae Matching' },
        { id: 'voice', name: 'Voice', icon: '🎤', weight: 0.20, description: 'Spectral Profiling' }
    ];

    const toggleModality = (id) => {
        if (selectedModalities.includes(id)) {
            setSelectedModalities(selectedModalities.filter(m => m !== id));
        } else {
            setSelectedModalities([...selectedModalities, id]);
        }
    };

    const startCapture = (id) => {
        setCurrentCapturing(id);
    };

    const handleCapture = async (id) => {
        let imageSrc = null;
        if (webcamRef.current) {
            imageSrc = webcamRef.current.getScreenshot();
        }

        if (imageSrc && id === 'face') {
            try {
                const bioType = 'facial';
                imageSrc = await cropBiometricImage(imageSrc, bioType);
            } catch (err) {
                console.error(`Multimodal capture crop failed for ${id}:`, err);
            }
        }

        setCapturedData({
            ...capturedData,
            [id]: {
                captured: true,
                image: imageSrc,
                timestamp: new Date().toLocaleTimeString(),
                score: (Math.random() * 20 + 80).toFixed(1) // Simulate high match scores
            }
        });
        setCurrentCapturing(null);
    };

    const performFusion = () => {
        if (selectedModalities.length < 2) return;

        setIsAuthenticating(true);
        setTimeout(() => {
            // Calculate weighted fusion score
            let totalWeight = 0;
            let weightedSum = 0;

            selectedModalities.forEach(m => {
                const mod = modalities.find(x => x.id === m);
                totalWeight += mod.weight;
                weightedSum += (parseFloat(capturedData[m]?.score) || 0) * mod.weight;
            });

            const finalScore = (weightedSum / totalWeight).toFixed(2);
            setFusionScore(finalScore);
            setIsAuthenticating(false);
        }, 2000);
    };

    const reset = () => {
        setCapturedData({});
        setFusionScore(null);
        setCurrentCapturing(null);
    };

    return (
        <div className="multimodal-container">
            <div className="header">
                <h1>🔬 Multimodal Biometric Fusion</h1>
                <p>Combines multiple biometric traits for ultra-high accuracy and spoof resistance.</p>
            </div>

            <div className="fusion-grid">
                <div className="selection-panel glass">
                    <h3>1. Select Modalities</h3>
                    <p className="hint">Choose at least 2 traits for fusion</p>
                    <div className="modality-list">
                        {modalities.map(m => (
                            <div
                                key={m.id}
                                className={`modality-card ${selectedModalities.includes(m.id) ? 'selected' : ''}`}
                                onClick={() => toggleModality(m.id)}
                            >
                                <div className="mod-icon">{m.icon}</div>
                                <div className="mod-info">
                                    <div className="mod-name">{m.name}</div>
                                    <div className="mod-weight">Weight: {m.weight * 100}%</div>
                                </div>
                                <div className="mod-check">
                                    <div className="checkbox"></div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                <div className="capture-panel glass">
                    <h3>2. Capture Data</h3>
                    <p className="hint">Complete capture for selected modalities</p>

                    <div className="capture-items">
                        {selectedModalities.map(mId => {
                            const mod = modalities.find(x => x.id === mId);
                            const data = capturedData[mId];

                            return (
                                <div key={mId} className={`capture-row ${data ? 'completed' : ''}`}>
                                    <div className="capture-info">
                                        <span className="icon">{mod.icon}</span>
                                        <span className="name">{mod.name}</span>
                                    </div>

                                    {data ? (
                                        <div className="capture-status success">
                                            <span>✓ Ready ({data.score}%)</span>
                                            <button className="btn-icon" onClick={() => startCapture(mId)}>🔄</button>
                                        </div>
                                    ) : (
                                        <button
                                            className="btn-capture"
                                            onClick={() => startCapture(mId)}
                                        >
                                            Start Capture
                                        </button>
                                    )}
                                </div>
                            );
                        })}
                    </div>

                    <div className="fusion-actions">
                        <input
                            type="text"
                            placeholder="Subject ID"
                            value={subjectId}
                            onChange={(e) => setSubjectId(e.target.value)}
                            className="id-input"
                        />
                        <button
                            className="btn-fusion"
                            disabled={selectedModalities.length < 2 || Object.keys(capturedData).length < selectedModalities.length || !subjectId}
                            onClick={performFusion}
                        >
                            Perform Fusion Authentication
                        </button>
                    </div>
                </div>

                <div className="result-panel glass">
                    <h3>3. Fusion Analysis</h3>

                    {isAuthenticating ? (
                        <div className="authenticating">
                            <div className="radar"></div>
                            <p>Calculating Fusion Score...</p>
                            <div className="fusion-stats">
                                {selectedModalities.map(mId => (
                                    <div key={mId} className="stat-line">
                                        Analyzing {mId} trait...
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : fusionScore ? (
                        <div className="fusion-result animate-scale-up">
                            <div className="score-circle">
                                <svg viewBox="0 0 100 100">
                                    <circle className="bg" cx="50" cy="50" r="45"></circle>
                                    <circle
                                        className="fg"
                                        cx="50"
                                        cy="50"
                                        r="45"
                                        style={{ strokeDashoffset: 283 - (283 * fusionScore) / 100 }}
                                    ></circle>
                                </svg>
                                <div className="score-value">{fusionScore}%</div>
                            </div>
                            <h2>{parseFloat(fusionScore) > 95 ? 'Highly Reliable Match' : 'Match Confirmed'}</h2>

                            <div className="modality-breakdown">
                                {selectedModalities.map(mId => {
                                    const mod = modalities.find(x => x.id === mId);
                                    return (
                                        <div key={mId} className="breakdown-row">
                                            <span>{mod.name}</span>
                                            <div className="mini-bar">
                                                <div className="fill" style={{ width: `${capturedData[mId].score}%` }}></div>
                                            </div>
                                            <span>{capturedData[mId].score}%</span>
                                        </div>
                                    );
                                })}
                            </div>

                            <button className="btn-secondary" onClick={reset}>New Session</button>
                        </div>
                    ) : (
                        <div className="placeholder-result">
                            <div className="pulse-icon">🔬</div>
                            <p>Complete the capture steps to view the multimodal fusion analysis.</p>
                        </div>
                    )}
                </div>
            </div>

            {currentCapturing && (
                <div className="capture-overlay animate-fade-in">
                    <div className="capture-modal glass">
                        <h2>Capturing {modalities.find(m => m.id === currentCapturing).name}</h2>

                        {currentCapturing === 'face' ? (
                            <div className="capture-viewport">
                                <Webcam
                                    audio={false}
                                    ref={webcamRef}
                                    screenshotFormat="image/jpeg"
                                    className="webcam"
                                />
                                <div className="viewport-overlay face"></div>
                            </div>
                        ) : currentCapturing === 'fingerprint' ? (
                            <div className="fingerprint-scan">
                                <div className="scan-line"></div>
                                <div className="finger-icon">👆</div>
                            </div>
                        ) : (
                            <div className="voice-scan">
                                <div className="waves">
                                    {[1, 2, 3, 4, 5].map(i => <div key={i} className="wave"></div>)}
                                </div>
                                <div className="mic-icon">🎤</div>
                            </div>
                        )}

                        <div className="modal-actions">
                            <button className="btn-secondary" onClick={() => setCurrentCapturing(null)}>Cancel</button>
                            <button className="btn-primary" onClick={() => handleCapture(currentCapturing)}>Confirm Capture</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default MultimodalAuth;
