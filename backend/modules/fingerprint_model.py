"""
Deep Fingerprint Recognition Model
Inspired by DeepFace architecture for high-accuracy biometric feature extraction.
Uses a Convolutional Neural Network (CNN) to extract 512-D embeddings from ridge patterns.
"""

import os
import numpy as np
from typing import Optional

try:
    import tensorflow as tf
    from tensorflow.keras import layers, models, regularizers
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False

class DeepFingerprintModel:
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.input_shape = (160, 160, 1)
        self.embedding_dim = 512
        
        if TF_AVAILABLE:
            if model_path and os.path.exists(model_path):
                self.load(model_path)
            else:
                self.model = self._build_architecture()
                print("[INFO] DeepFingerprint: Built new architecture (uninitialized)")

    def _build_architecture(self):
        """
        Builds a deep residual network optimized for fingerprint ridge patterns.
        Similar to FaceNet/ArcFace architectures.
        """
        inputs = layers.Input(shape=self.input_shape)
        
        # Initial Convolution
        x = layers.Conv2D(32, (3, 3), padding='same', use_bias=False)(inputs)
        x = layers.BatchNormalization()(x)
        x = layers.Activation('relu')(x)
        
        # Residual Blocks
        def res_block(x, filters, kernel_size=(3, 3), strides=(1, 1)):
            shortcut = x
            if strides != (1, 1) or shortcut.shape[-1] != filters:
                shortcut = layers.Conv2D(filters, (1, 1), strides=strides, padding='same')(shortcut)
                shortcut = layers.BatchNormalization()(shortcut)
            
            x = layers.Conv2D(filters, kernel_size, strides=strides, padding='same', use_bias=False)(x)
            x = layers.BatchNormalization()(x)
            x = layers.Activation('relu')(x)
            
            x = layers.Conv2D(filters, kernel_size, padding='same', use_bias=False)(x)
            x = layers.BatchNormalization()(x)
            
            x = layers.Add()([x, shortcut])
            x = layers.Activation('relu')(x)
            return x

        x = res_block(x, 64, strides=(2, 2))
        x = res_block(x, 64)
        x = res_block(x, 128, strides=(2, 2))
        x = res_block(x, 128)
        x = res_block(x, 256, strides=(2, 2))
        x = res_block(x, 256)
        x = res_block(x, 512, strides=(2, 2))
        x = res_block(x, 512)
        
        # Global Pooling + Embedding Head
        x = layers.GlobalAveragePooling2D()(x)
        x = layers.Dropout(0.4)(x)
        
        # Embedding Layer
        x = layers.Dense(self.embedding_dim, use_bias=False, name='embedding')(x)
        x = layers.BatchNormalization(name='embedding_bn')(x)
        
        # L2 Normalization (Crucial for cosine similarity matching)
        outputs = layers.Lambda(lambda x: tf.math.l2_normalize(x, axis=1), name='l2_norm')(x)
        
        model = models.Model(inputs, outputs, name="DeepFingerprintNet")
        return model

    def extract_features(self, img_path_or_array) -> Optional[np.ndarray]:
        """Extract 512-D normalized embedding from fingerprint image"""
        if not TF_AVAILABLE or self.model is None:
            return None
            
        try:
            # Load and preprocess image
            if isinstance(img_path_or_array, str):
                import cv2
                img = cv2.imread(img_path_or_array, cv2.IMREAD_GRAYSCALE)
            else:
                img = img_path_or_array
                
            if img is None:
                return None
                
            # Resize and normalize
            img = cv2.resize(img, (self.input_shape[1], self.input_shape[0]))
            img = img.astype('float32') / 255.0
            img = np.expand_dims(img, axis=(0, -1)) # Add batch and channel dims
            
            # Inference
            embedding = self.model.predict(img, verbose=0)
            return embedding[0]
        except Exception as e:
            print(f"[ERR] DeepFingerprint extraction failed: {e}")
            return None

    def save(self, path: str):
        if self.model:
            self.model.save(path)
            print(f"[OK] DeepFingerprint model saved to {path}")

    def load(self, path: str):
        if TF_AVAILABLE:
            self.model = models.load_model(path, compile=False)
            print(f"[OK] DeepFingerprint model loaded from {path}")

# Global singleton
fingerprint_deep_model = DeepFingerprintModel()
