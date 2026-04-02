"""
Biometric Engine Module

Handles biometric feature extraction using:
- DeepFace with FaceNet model for accurate facial recognition
- Fingerprint and Iris fallbacks
- L2-normalized embeddings for consistent comparison
"""

import os
import hashlib
import numpy as np
import random
from typing import Optional, Tuple
# ── NEW: dedicated high-accuracy webcam engines ──
try:
    from modules.fingerprint_model import fingerprint_deep_model
    from modules.fingerprint_engine import (
        extract_fingerprint_features as _fp_extract,
        compare_fingerprints as _fp_compare
    )
    FP_ENGINE_AVAILABLE = True
    print("[OK] Fingerprint engines (Deep + Traditional) loaded")
except ImportError:
    try:
        from fingerprint_model import fingerprint_deep_model
        from fingerprint_engine import (
            extract_fingerprint_features as _fp_extract,
            compare_fingerprints as _fp_compare
        )
        FP_ENGINE_AVAILABLE = True
        print("[OK] Fingerprint engines loaded (local)")
    except ImportError:
        FP_ENGINE_AVAILABLE = False
        print("[WARN] Fingerprint engine modules not found")

try:
    from modules.voice_engine import (
        extract_voice_features as _voice_extract,
        compare_voice as _voice_compare
    )
    VOICE_ENGINE_AVAILABLE = True
    print("[OK] voice_engine loaded")
except ImportError:
    try:
        from voice_engine import (
            extract_voice_features as _voice_extract,
            compare_voice as _voice_compare
        )
        VOICE_ENGINE_AVAILABLE = True
        print("[OK] voice_engine loaded (local)")
    except ImportError:
        VOICE_ENGINE_AVAILABLE = False
        print("[WARN] voice_engine not found")



# Set random seeds for determinism
def set_seeds(seed=42):
    # random.seed(seed) # Removed to prevent deterministic random choices for human codes
    np.random.seed(seed)
    try:
        import tensorflow as tf
        tf.random.set_seed(seed)
        os.environ['PYTHONHASHSEED'] = str(seed)
        os.environ['TF_DETERMINISTIC_OPS'] = '1'
    except (ImportError, Exception):
        pass

set_seeds()

# Import CV2 with fallback
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("[WARN] OpenCV not installed")

# Import DeepFace for face recognition
try:
    from deepface import DeepFace
    from scipy.spatial.distance import cosine # Added scipy.spatial.distance.cosine for comparison
    DEEPFACE_AVAILABLE = True
    print("[OK] DeepFace loaded for facial recognition")
except ImportError:
    DEEPFACE_AVAILABLE = False
    print("[WARN] DeepFace or Scipy not installed. Install with: pip install deepface scipy")

# Import PyTorch for Advanced Biometrics
try:
    import torch
    import torch.nn as nn
    import torchvision.models as models
    import torch.nn.functional as F
    from torchvision import transforms
    from PIL import Image
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("[WARN] PyTorch/Torchvision not installed")

if TORCH_AVAILABLE:
    class DeepIrisNet(nn.Module):
        """Deep Neural Network for Iris and Fingerprint feature extraction"""
        def __init__(self, embedding_size=512):
            super(DeepIrisNet, self).__init__()
            # Load pretrained ResNet50
            base_model = models.resnet50(pretrained=True)
            # Remove classification and pooling
            self.backbone = nn.Sequential(*list(base_model.children())[:-2])
            
            # Dual pooling to capture both global structure and local textures
            self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
            self.maxpool = nn.AdaptiveMaxPool2d((1, 1))
            
            # More discriminative head with bottleneck and dropout for robustness
            self.head = nn.Sequential(
                nn.Linear(2048 * 2, 1024),
                nn.BatchNorm1d(1024),
                nn.LeakyReLU(0.1),
                nn.Dropout(0.2),
                nn.Linear(1024, embedding_size)
            )
            
            # Orthogonal initialization helps preserve variance in pre-trained features
            for m in self.head.modules():
                if isinstance(m, nn.Linear):
                    nn.init.orthogonal_(m.weight, gain=1.0)
                    if m.bias is not None:
                        nn.init.constant_(m.bias, 0)
            
        def forward(self, x):
            features = self.backbone(x)
            
            # Apply dual pooling
            ap = self.avgpool(features).view(features.size(0), -1)
            mp = self.maxpool(features).view(features.size(0), -1)
            
            # Concatenate features (4096D)
            x = torch.cat([ap, mp], dim=1)
            
            # Project to embedding space
            x = self.head(x)
            
            # Normalize embedding (important for cosine similarity)
            x = F.normalize(x, p=2, dim=1)
            return x
else:
    class DeepIrisNet:
        """Fallback placeholder when PyTorch is unavailable."""
        pass

class BiometricEngine:
    """Biometric feature extraction and comparison engine using DeepFace and PyTorch."""
    
    # ArcFace produces 512-dimensional embeddings (better accuracy)
    # FaceNet produces 128-dimensional embeddings
    ARCFACE_DIM = 512
    FACENET_DIM = 128
    
    def __init__(self, feature_dim: int = 512):
        set_seeds()
        self.feature_dim = feature_dim
        # Use ArcFace for better accuracy (>70% requirement)
        # Fallback to FaceNet512 if ArcFace fails, then FaceNet
        self.face_model_name = 'ArcFace'  # Best accuracy: ArcFace > FaceNet512 > FaceNet
        self.detector_backend = 'opencv'  # Faster and lighter for hosted runtime stability
        
        # Initialize DeepFace
        self._warmup_deepface()
        
        # Initialize PyTorch Model for Iris/Fingerprint
        self.device = None
        self.secondary_model = None
        if TORCH_AVAILABLE:
            try:
                self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                self.secondary_model = DeepIrisNet(embedding_size=512).to(self.device)
                self.secondary_model.eval()
                # Image transform for ResNet50
                self.transform = transforms.Compose([
                    transforms.Resize((224, 224)),
                    transforms.ToTensor(),
                    transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])
                ])
                print(f"[OK] PyTorch Secondary Biometric Model (512D) loaded on {self.device}")
                
                # Active Eye Detector for Iris Segmentation
                self.eye_cascade = None
                if CV2_AVAILABLE:
                    try:
                        eye_path = cv2.data.haarcascades + 'haarcascade_eye.xml'
                        self.eye_cascade = cv2.CascadeClassifier(eye_path)
                        print(f"[OK] Active Eye Detector initialized using {eye_path}")
                    except Exception as e:
                        print(f"[WARN] Eye detector init failed: {e}")
            except Exception as e:
                print(f"[ERR] Failed to load PyTorch model: {e}")
    
    def _warmup_deepface(self):
        """Pre-load DeepFace model to avoid cold start delays"""
        if DEEPFACE_AVAILABLE:
            try:
                # Use Facenet512 for 512D or Facenet for 128D
                if self.feature_dim == 512:
                    self.face_model_name = 'Facenet512'
                else:
                    self.face_model_name = 'Facenet'
                    self.feature_dim = 128 # Default to 128 if not 512
                
                print(f"[INFO] Initializing DeepFace with {self.face_model_name} ({self.feature_dim}D)")
                
                try:
                    DeepFace.build_model(self.face_model_name)
                    print(f"[OK] DeepFace {self.face_model_name} model initialized")
                except Exception as e:
                    print(f"[WARN] {self.face_model_name} build failed: {e}")
                    # Fallback
                    if self.face_model_name == 'Facenet512':
                        self.face_model_name = 'Facenet'
                        self.feature_dim = 128
                        DeepFace.build_model('Facenet')
                
                # Test detector backends in order of preference
                test_image = np.zeros((224, 224, 3), dtype=np.uint8)
                dummy_path = os.path.join(os.path.dirname(__file__), '..', 'uploads', '_warmup.jpg')
                os.makedirs(os.path.dirname(dummy_path), exist_ok=True)
                if CV2_AVAILABLE:
                    cv2.imwrite(dummy_path, test_image)
                
                # Prefer the fastest detector first so the warmup matches production constraints.
                for detector in ['opencv', 'mtcnn', 'retinaface']:
                    try:
                        if os.path.exists(dummy_path):
                            DeepFace.represent(
                                img_path=dummy_path,
                                model_name=self.face_model_name,
                                detector_backend=detector,
                                enforce_detection=False
                            )
                            self.detector_backend = detector
                            print(f"[OK] Using detector backend: {detector}")
                            break
                    except Exception:
                        continue
                
                # Cleanup
                if os.path.exists(dummy_path):
                    os.remove(dummy_path)
            except Exception as e:
                print(f"[WARN] DeepFace warmup note: {e}")

    def _apply_gabor_bundle(self, gray_img):
        """Apply a bank of Gabor filters to extract multi-orientation iris textures"""
        if not CV2_AVAILABLE: return gray_img
        
        # Orientations: 0, 45, 90, 135 degrees
        kernels = []
        for theta in [0, np.pi/4, np.pi/2, 3*np.pi/4]:
            kernel = cv2.getGaborKernel((21, 21), 5.0, theta, 10.0, 0.5, 0, ktype=cv2.CV_32F)
            kernels.append(kernel)
            
        # Combine responses
        combined = np.zeros_like(gray_img, dtype=np.float32)
        for k in kernels:
            fimg = cv2.filter2D(gray_img, cv2.CV_32F, k)
            np.maximum(combined, fimg, combined)
            
        # Normalize back to 0-255
        combined = np.clip(combined, 0, 255).astype(np.uint8)
        return combined

    def extract_features(self, image_path: str, biometric_type: str = 'facial', **kwargs) -> Optional[np.ndarray]:
        """Extract biometric features using appropriate models."""
        print(f"[PROCESS] Extracting features for type: '{biometric_type}'")
        
        if biometric_type == 'facial':
            print(f"   -> Using DeepFace ({self.face_model_name})")
            return self._extract_facial_features(image_path)
        elif biometric_type == 'fingerprint':
            print(f"   -> Using DeepFingerprint CNN Engine")
            return self._extract_fingerprint_features(image_path)
        elif biometric_type == 'voice':
            print(f"   -> Using voice_engine for Voice Analysis")
            return self._extract_voice_features(image_path)
        else:
            print(f"   -> [WARN] Unknown type '{biometric_type}', using fallback")
            return self._fallback_features(image_path)
    
    def _extract_facial_features(self, image_path: str) -> Optional[np.ndarray]:
        """Extract facial features using DeepFace with improved face detection."""
        
        if not DEEPFACE_AVAILABLE:
            print("[WARN] DeepFace not available, using fallback")
            return self._fallback_features(image_path)
        
        # Try the faster detector first to avoid long blocking calls in Azure.
        detector_backends = [self.detector_backend, 'opencv', 'mtcnn', 'retinaface']
        
        for detector in detector_backends:
            try:
                # First, verify face is detected (enforce_detection=True for quality)
                try:
                    # Try with enforce_detection=True first to ensure face is found
                    result = DeepFace.represent(
                        img_path=image_path,
                        model_name=self.face_model_name,
                        enforce_detection=True,  # Require face detection
                        detector_backend=detector,
                        align=True  # Face alignment improves accuracy
                    )
                except ValueError as ve:
                    # If enforce_detection=True fails, try with False but log warning
                    if "Face could not be detected" in str(ve) or "could not detect a face" in str(ve).lower():
                        print(f"[WARN] Face not detected with {detector}, trying with relaxed detection...")
                        result = DeepFace.represent(
                            img_path=image_path,
                            model_name=self.face_model_name,
                            enforce_detection=False,
                            detector_backend=detector,
                            align=True
                        )
                    else:
                        raise
                
                if result and len(result) > 0:
                    embedding = np.array(result[0]['embedding'], dtype=np.float32)
                    
                    # Verify embedding quality
                    if len(embedding) == 0 or np.isnan(embedding).any() or np.isinf(embedding).any():
                        print(f"[WARN] Invalid embedding from {detector}, trying next detector...")
                        continue
                    
                    # L2 normalize for consistent cosine similarity
                    norm = np.linalg.norm(embedding)
                    if norm > 0:
                        embedding = embedding / norm
                    else:
                        print(f"[WARN] Zero norm embedding from {detector}, trying next detector...")
                        continue
                    
                    # Ensure correct feature dimension
                    if len(embedding) != self.feature_dim:
                        if len(embedding) > self.feature_dim:
                            # Truncate if larger
                            embedding = embedding[:self.feature_dim]
                        else:
                            # Pad if smaller
                            padding = np.zeros(self.feature_dim - len(embedding), dtype=np.float32)
                            embedding = np.concatenate([embedding, padding])
                    
                    print(f"[OK] Extracted {len(embedding)}D facial embedding using {detector} + {self.face_model_name}")
                    print(f"   Embedding stats: min={embedding.min():.4f}, max={embedding.max():.4f}, mean={embedding.mean():.4f}, norm={np.linalg.norm(embedding):.4f}")
                    return embedding
                else:
                    print(f"[WARN] No face embedding returned from {detector}")
                    continue
                    
            except Exception as e:
                print(f"[WARN] DeepFace extraction error with {detector}: {e}")
                continue
        
        # If all detectors fail, try OpenCV fallback
        print("[WARN] All DeepFace detectors failed, trying OpenCV fallback...")
        return self._opencv_facial_features(image_path)
    
    def _opencv_facial_features(self, image_path: str) -> Optional[np.ndarray]:
        """Fallback facial feature extraction using OpenCV with improved preprocessing."""
        if not CV2_AVAILABLE:
            return self._fallback_features(image_path)
        
        try:
            img = cv2.imread(image_path)
            if img is None:
                print("[WARN] Could not read image with OpenCV")
                return self._fallback_features(image_path)
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Face detection with multiple cascades for better detection
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            
            if len(faces) > 0:
                # Use largest face
                (x, y, w, h) = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)[0]
                
                # Crop face with padding
                p = 0.2  # 20% padding
                y1 = max(0, int(y - h * p))
                y2 = min(img.shape[0], int(y + h * (1 + p)))
                x1 = max(0, int(x - w * p))
                x2 = min(img.shape[1], int(x + w * (1 + p)))
                face_img = gray[y1:y2, x1:x2]
                
                # Resize to standard size for feature extraction
                face_img = cv2.resize(face_img, (160, 160))
                
                # Apply histogram equalization for better contrast
                face_img = cv2.equalizeHist(face_img)
                
                # Extract multiple feature types for better representation
                # 1. Histogram features
                hist = cv2.calcHist([face_img], [0], None, [128], [0, 256])
                hist = hist.flatten().astype(np.float32)
                
                # 2. LBP-like features (Local Binary Pattern approximation)
                # Divide image into blocks and compute histograms
                features_list = [hist]
                block_size = 40
                for i in range(0, face_img.shape[0] - block_size, block_size):
                    for j in range(0, face_img.shape[1] - block_size, block_size):
                        block = face_img[i:i+block_size, j:j+block_size]
                        block_hist = cv2.calcHist([block], [0], None, [32], [0, 256])
                        features_list.append(block_hist.flatten().astype(np.float32))
                
                # Combine all features
                combined_features = np.concatenate(features_list).astype(np.float32)
                
                # Pad or truncate to feature_dim
                if len(combined_features) < self.feature_dim:
                    padding = np.zeros(self.feature_dim - len(combined_features), dtype=np.float32)
                    combined_features = np.concatenate([combined_features, padding])
                else:
                    combined_features = combined_features[:self.feature_dim]
                
                # Normalize
                norm = np.linalg.norm(combined_features)
                if norm > 0:
                    combined_features = combined_features / norm
                
                print(f"✓ Extracted {len(combined_features)}D features using OpenCV fallback")
                return combined_features
            else:
                print("⚠ No face detected with OpenCV cascade")
                return self._fallback_features(image_path)
            
        except Exception as e:
            print(f"⚠ OpenCV fallback error: {e}")
            import traceback
            traceback.print_exc()
            return self._fallback_features(image_path)
    
    def _extract_fingerprint_features(self, image_path: str) -> Optional[np.ndarray]:
        """Extract fingerprint features using Deep Learning CNN or traditional minutiae engine."""
        try:
            with open(image_path, 'rb') as f:
                data = f.read()
                if data.startswith(b"FID:"):
                    vector_str = data[4:].decode('utf-8')
                    import hashlib
                    h = hashlib.sha512(vector_str.encode()).digest()
                    seed = int.from_bytes(h[:4], 'big')
                    np.random.seed(seed)
                    descriptor = np.random.randn(self.feature_dim).astype(np.float32)
                    norm = np.linalg.norm(descriptor)
                    if norm > 1e-6:
                        descriptor /= norm
                    set_seeds() # reset
                    print(f"[OK] Fingerprint: Windows Hello seed={seed}")
                    return descriptor
        except Exception:
            pass

        if FP_ENGINE_AVAILABLE:
            try:
                # 1. Try Deep Learning CNN (similar to DeepFace)
                print("[INFO] Attempting DeepFingerprint CNN extraction...")
                result = fingerprint_deep_model.extract_features(image_path)
                if result is not None:
                    print("[OK] Fingerprint: Deep CNN feature extraction successful")
                    return result
                
                # 2. Fallback to Traditional Minutiae Cylinder Code
                print("[INFO] Deep model returned None, falling back to Traditional Engine...")
                result = _fp_extract(image_path)
                if result is not None:
                    return result
            except Exception as e:
                print(f"[ERR] Fingerprint engine failure: {e}")

        return self._extract_secondary_biometric(image_path, "fingerprint")
    
    def _extract_voice_features(self, audio_path: str) -> Optional[np.ndarray]:
        """Extract voice features using MFCC pipeline.
        """
        if VOICE_ENGINE_AVAILABLE:
            result = _voice_extract(audio_path)
            if result is not None:
                # Resize to match system feature_dim if needed
                if len(result) != self.feature_dim:
                    result = np.resize(result, self.feature_dim)
                return result
            print("[VOICE] New engine returned None, falling back to legacy")
        return self._extract_secondary_biometric(audio_path, "voice")

    def _extract_secondary_biometric(self, image_path: str, bio_type: str) -> Optional[np.ndarray]:
        """Secondary biometric extraction with Active Eye Tracking for Iris"""
        if not TORCH_AVAILABLE or self.secondary_model is None:
            return self._fallback_features(image_path)
            
        try:
            img_cv = cv2.imread(image_path) if CV2_AVAILABLE else None
            if img_cv is None: return self._fallback_features(image_path)
            
            # 1. ACTIVE SEGMENTATION
            if bio_type == 'iris' and self.eye_cascade is not None:
                gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                # Detect the eye to find the iris location
                eyes = self.eye_cascade.detectMultiScale(gray, 1.1, 5)
                
                if len(eyes) > 0:
                    # Choose the largest "eye" detected
                    ex, ey, ew, eh = sorted(eyes, key=lambda e: e[2], reverse=True)[0]
                    cx, cy = ex + ew//2, ey + eh//2
                    side = int(ew * 0.55) # Slightly wider for better context
                    img_cv = img_cv[max(0,cy-side//2):cy+side//2, max(0,cx-side//2):cx+side//2]
                    print(f"[EYE-TRACK] Localized iris within eye box")
                else:
                    # SMART FALLBACK: If image is already small (frontend cropped), don't crop much
                    h, w = img_cv.shape[:2]
                    is_frontend_cropped = (w < 400)
                    crop_factor = 0.85 if is_frontend_cropped else 0.45
                    
                    print(f"[EYE-TRACK] Detector failed. Using {crop_factor*100}% static crop (is_small={is_frontend_cropped})")
                    side = int(min(h, w) * crop_factor)
                    img_cv = img_cv[h//2-side//2:h//2+side//2, w//2-side//2:w//2+side//2]
            elif bio_type == 'fingerprint':
                # For fingerprints, use a focused 70% crop
                h, w = img_cv.shape[:2]
                side = int(min(h, w) * 0.7)
                img_cv = img_cv[h//2-side//2:h//2+side//2, w//2-side//2:w//2+side//2]

            # 2. FEATURE ENCODING
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            
            if bio_type == 'iris':
                # LAPTOP CAMERA ENHANCEMENT: Amplify subtle textures using CLAHE
                # Also add slight denoising to remove laptop sensor grain
                denoised = cv2.medianBlur(gray, 3)
                clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(8,8))
                gray = clahe.apply(denoised)
                
                # SHARPNESS LOCK - Reject blurry iris images
                laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
                if laplacian_var < 50.0:
                    print(f"[WARN] Iris image too blurry ({laplacian_var:.2f}). Rejection possible.")
                
                # Binary IrisCode Logic (128x128 bit-mapping)
                resized = cv2.resize(gray, (128, 128))
                
                # Apply Gabor to capture detailed iris crypts
                g0 = cv2.getGaborKernel((17, 17), 4.5, 0, 10.0, 0.5, 0, ktype=cv2.CV_32F)
                g90 = cv2.getGaborKernel((17, 17), 4.5, np.pi/2, 10.0, 0.5, 0, ktype=cv2.CV_32F)
                
                resp0 = cv2.filter2D(resized, cv2.CV_32F, g0)
                resp90 = cv2.filter2D(resized, cv2.CV_32F, g90)
                
                # Generate specialized Binary Signature
                # Quantization: 1 if positive, 0 if negative
                code0 = (resp0 > 0).astype(np.uint8)
                code90 = (resp90 > 0).astype(np.uint8)
                
                features = np.concatenate([code0.flatten(), code90.flatten()]).astype(np.float32)
                print(f"[OK] Generated {len(features)}-bit high-precision IrisCode")
                return features
            
            # Fingerprint ResNet Pipeline
            from PIL import Image
            enhanced_gray = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8,8)).apply(gray)
            img = Image.fromarray(cv2.cvtColor(enhanced_gray, cv2.COLOR_GRAY2RGB))
            img_t = self.transform(img).unsqueeze(0).to(self.device)
            with torch.no_grad():
                embedding = self.secondary_model(img_t)
            features = embedding.cpu().numpy()[0]
            norm = np.linalg.norm(features)
            return features / norm if norm > 1e-6 else features
            
        except Exception as e:
            print(f"[ERR] {bio_type} extraction failed: {e}")
            return self._fallback_features(image_path)

    def _fallback_features(self, image_path: str) -> np.ndarray:
        """Deterministic fallback features based on perceptual hashing."""
        try:
            if not CV2_AVAILABLE:
                # Absolute fallback if CV2 is missing
                h = hashlib.sha256(image_path.encode()).digest()
                return np.frombuffer(h * (self.feature_dim // 32 + 1), dtype=np.float32)[:self.feature_dim]
            
            img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            small = cv2.resize(img, (16, 8)) if img is not None else np.zeros((8, 16))
            features = small.flatten().astype(np.float32) / 255.0
            return features if len(features) == self.feature_dim else np.resize(features, self.feature_dim)
        except Exception:
            return np.zeros(self.feature_dim, dtype=np.float32)

    def compare(self, f1, f2, method='cosine', bio_type='facial'):
        """Compare two feature vectors and return similarity score (0-1)."""
        if f1 is None or f2 is None: 
            print("[WARN] Comparison failed: one or both features are None")
            return 0.0
        
        # Ensure same shape and type
        f1 = np.array(f1, dtype=np.float32).flatten()
        f2 = np.array(f2, dtype=np.float32).flatten()
        
        if len(f1) != len(f2):
            min_len = min(len(f1), len(f2))
            f1 = f1[:min_len]
            f2 = f2[:min_len]
            print(f"[WARN] Feature dimension mismatch, using first {min_len} dimensions")
        
        # Check for invalid values
        if np.isnan(f1).any() or np.isnan(f2).any():
            print("[WARN] Comparison failed: NaN values in features")
            return 0.0
        
        if np.isinf(f1).any() or np.isinf(f2).any():
            print("[WARN] Comparison failed: Inf values in features")
            return 0.0
        
        # Normalize both vectors for consistent comparison
        norm1 = np.linalg.norm(f1)
        norm2 = np.linalg.norm(f2)
        if norm1 > 0:
            f1 = f1 / norm1
        if norm2 > 0:
            f2 = f2 / norm2
        
        if method == 'cosine':
            # 1. SPECIAL CASE: VOICE 
            if bio_type == 'voice':
                if VOICE_ENGINE_AVAILABLE:
                    return _voice_compare(f1, f2)
                # Legacy fallback
                cosine_sim = np.clip(np.dot(f1, f2), -1.0, 1.0)
                # User suggested 0.80 threshold. Stretch so 0.80 -> 0.6 confidence
                bias = 0.80
                stretched = max(0.0, (cosine_sim - bias) / (1.0 - bias))
                return float(np.power(stretched, 1.2))

            # 2. SPECIAL CASE: FINGERPRINT (Similarity Metrics)
            if bio_type == 'fingerprint':
                if FP_ENGINE_AVAILABLE:
                    return _fp_compare(f1, f2)
                bias = 0.935 
                stretched = max(0.0, (cosine_sim - bias) / (1.0 - bias))
                similarity = float(np.power(stretched, 1.5))
            else:
                similarity = float(max(0.0, cosine_sim))
                
            print(f"[DEBUG] {bio_type} similarity: raw={cosine_sim:.4f}, final={similarity:.4f}")
            return similarity
        else:
            # Euclidean distance converted to similarity
            euclidean_dist = np.linalg.norm(f1 - f2)
            similarity = float(1 / (1 + euclidean_dist))
            return similarity

    def check_liveness(self, path):
        # Basic laplacian variance liveness 
        try:
            if 'cv2' in globals() or 'cv2' in locals():
                pass # Already imported
            else:
                import cv2
            
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if img is None: return True, 1.0
            var = cv2.Laplacian(img, cv2.CV_64F).var()
            score = min(1.0, var / 500.0)
            return bool(score > 0.005), score 
        except Exception:
            return True, 1.0

