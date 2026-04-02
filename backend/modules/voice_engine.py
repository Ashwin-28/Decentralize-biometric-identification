import os
import numpy as np
import librosa
import hashlib
import json
import speech_recognition as sr
from scipy.spatial.distance import cosine
from scipy.stats import pearsonr

VOICE_AUTH_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "userId", "type": "string"},
            {"internalType": "string", "name": "hashValue", "type": "string"}
        ],
        "name": "storeHash",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "string", "name": "userId", "type": "string"}
        ],
        "name": "getHash",
        "outputs": [
            {"internalType": "string", "name": "", "type": "string"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

# ─────────────────────────────────────────────
# STEP 1: Extract stable MFCC voice fingerprint
# ─────────────────────────────────────────────
def extract_voice_features(audio_path: str) -> np.ndarray:
    """
    Extracts a stable MFCC-based voice fingerprint from an audio file.
    Returns a normalized 1D feature vector.
    """
    try:
        # force 16kHz for consistency
        y, sr_rate = librosa.load(audio_path, sr=16000)

        # Remove silence — critical for stability
        y, _ = librosa.effects.trim(y, top_db=20)

        # Extract MFCCs (40 coefficients for better accuracy)
        mfccs = librosa.feature.mfcc(y=y, sr=sr_rate, n_mfcc=40)

        # Use mean + std across time → stable despite recording length differences
        mfcc_mean = np.mean(mfccs, axis=1)
        mfcc_std  = np.std(mfccs, axis=1)

        # Also extract pitch (fundamental frequency) as extra feature
        # Note: pyin can be slow, but it's more accurate for pitch
        f0, voiced_flag, voiced_probs = librosa.pyin(y, fmin=80, fmax=400, sr=sr_rate)
        f0 = f0[~np.isnan(f0)]  # drop NaN frames
        pitch_mean = np.mean(f0) if len(f0) > 0 else 0.0
        pitch_std  = np.std(f0)  if len(f0) > 0 else 0.0

        # Combine into one feature vector
        features = np.concatenate([mfcc_mean, mfcc_std, [pitch_mean, pitch_std]])

        # L2 normalize so cosine similarity works correctly
        norm = np.linalg.norm(features)
        return features / norm if norm > 0 else features
    except Exception as e:
        print(f"[VOICE-BIOMETRIC] ❌ Error in extraction: {e}")
        # Return a zero vector of the expected size (40 mean + 40 std + 2 pitch = 82)
        return np.zeros(82)

# ─────────────────────────────────────────────
# STEP 2: Hash features for blockchain storage
# ─────────────────────────────────────────────
def features_to_hash(features: np.ndarray, precision: int = 4) -> str:
    """
    Converts feature vector to a deterministic hash for blockchain storage.
    `precision` controls rounding — higher = stricter matching.
    Recommended: 3 or 4
    """
    # Round to reduce floating-point noise between recordings
    rounded = np.round(features.astype(float), decimals=precision).tolist()
    feature_str = json.dumps(rounded, separators=(',', ':'))
    return hashlib.sha256(feature_str.encode()).hexdigest()

# ─────────────────────────────────────────────
# STEP 3: Verification — compare voice samples
# ─────────────────────────────────────────────
def verify_voice(
    live_audio_path: str,
    stored_vector: list,
    threshold: float = 0.82
) -> dict:
    """
    Call this during login/verification.
    Returns dict with match result + confidence score.
    """
    live_features   = extract_voice_features(live_audio_path)
    stored_features = np.array(stored_vector)

    # If extraction failed or vectors don't match in size
    if len(live_features) != len(stored_features):
        return {
            "matched": False,
            "confidence": 0.0,
            "status": "❌ Vector Mismatch (Internal Error)"
        }

    confidence = compare_voice(live_features, stored_features)
    matched    = confidence >= threshold

    return {
        "matched":    matched,
        "confidence": round(float(confidence), 4),
        "threshold":  threshold,
        "status":     "✅ Voice Verified" if matched else "❌ Voice Mismatch"
    }

def compare_voice(live_features: np.ndarray, stored_features: np.ndarray) -> float:
    """
    Compares two feature vectors using Cosine Similarity and Pearson Correlation.
    Used by both verify_voice and BiometricEngine.
    """
    try:
        # Cosine similarity (1.0 = identical, 0.0 = completely different)
        similarity = 1 - cosine(live_features, stored_features)

        # Pearson correlation as a second check
        corr, _ = pearsonr(live_features, stored_features)

        # Weighted confidence score
        confidence = (similarity * 0.7) + (corr * 0.3)
        return float(confidence)
    except Exception as e:
        print(f"[VOICE-COMPARE] Error: {e}")
        return 0.0

# ─────────────────────────────────────────────
# STEP 4: (Optional) Blockchain hash integrity check
# ─────────────────────────────────────────────
def verify_hash_integrity(stored_vector: list, stored_hash: str) -> bool:
    """
    Confirms the stored vector hasn't been tampered with on-chain.
    """
    features = np.array(stored_vector)
    recomputed_hash = features_to_hash(features)
    return recomputed_hash == stored_hash

# ─────────────────────────────────────────────
# Pre-checks & Liveness
# ─────────────────────────────────────────────
def simple_liveness_check(file_path: str) -> bool:
    """
    Ensures that the audio has sufficient volume/activity (not silence).
    """
    try:
        y, _ = librosa.load(file_path, sr=16000)
        max_amplitude = np.max(np.abs(y))
        print(f"[VOICE-LIVENESS] Max Amplitude: {max_amplitude:.4f}")
        
        # Threshold for physical presence detection
        if max_amplitude > 0.02:
            print("✅ Liveness OK")
            return True
        else:
            print("❌ No voice detected (Liveness Failed)")
            return False
    except Exception as e:
        print(f"[VOICE-LIVENESS] Error: {e}")
        return False

def get_voice_duration(file_path: str) -> float:
    try:
        y, sr_val = librosa.load(file_path, sr=None)
        duration = librosa.get_duration(y=y, sr=sr_val)
        return float(duration)
    except Exception:
        return 0.0

def speech_to_text(file_path: str) -> str:
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(file_path) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
            return text.lower().strip()
    except:
        return ""
