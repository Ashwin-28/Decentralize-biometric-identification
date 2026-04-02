"""
Machine Learning Training Module for Biometric Recognition
Supports training facial, fingerprint, and iris recognition models
"""

import os
import json
import uuid
import hashlib
import threading
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable

# TensorFlow imports with fallback
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers, models, optimizers, callbacks
    from tensorflow.keras.preprocessing.image import ImageDataGenerator
    TF_AVAILABLE = True
    print(f"[OK] TensorFlow {tf.__version__} loaded for ML training")
except ImportError:
    TF_AVAILABLE = False
    print("[WARN] TensorFlow not available. Install with: pip install tensorflow")

# OpenCV for image processing
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("[WARN] OpenCV not available")

# Sklearn for metrics
try:
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, confusion_matrix, precision_recall_fscore_support
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("[WARN] Scikit-learn not available. Install with: pip install scikit-learn")


class BiometricModelTrainer:
    """Trainer for biometric recognition models"""
    
    # Model configurations
    MODEL_CONFIGS = {
        'facial': {
            'input_shape': (224, 224, 3),
            # Match production facial embedding dimensionality (ArcFace/DeepFace uses 512D)
            'embedding_dim': 512,
            'architecture': 'ArcFace-Style Embedding (512D)',
            'default_epochs': 50,
            'batch_size': 32
        },
        'fingerprint': {
            'input_shape': (128, 128, 1),
            'embedding_dim': 64,
            'architecture': 'Minutiae CNN',
            'default_epochs': 30,
            'batch_size': 64
        },
        'iris': {
            'input_shape': (64, 512, 1),
            'embedding_dim': 256,
            'architecture': 'IrisCode CNN',
            'default_epochs': 40,
            'batch_size': 32
        }
    }
    
    def __init__(self, models_dir: str = 'models', data_dir: str = 'training_data'):
        self.models_dir = Path(models_dir)
        self.data_dir = Path(data_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.training_jobs: Dict[str, dict] = {}
        self.active_model = {}
        
        # Database service
        from .database import db_service
        self.db = db_service
        
        print(f"[OK] ML Trainer initialized (TensorFlow: {TF_AVAILABLE})")
    
    # ==================== Model Architecture Builders ====================
    
    def build_facial_model(self) -> Optional['keras.Model']:
        """Build FaceNet-style facial recognition model"""
        if not TF_AVAILABLE:
            return None
        
        config = self.MODEL_CONFIGS['facial']
        input_shape = config['input_shape']
        embedding_dim = config['embedding_dim']
        
        # Input layer
        inputs = layers.Input(shape=input_shape, name='face_input')
        
        # Convolutional blocks
        x = layers.Conv2D(32, (3, 3), activation='relu', padding='same')(inputs)
        x = layers.BatchNormalization()(x)
        x = layers.MaxPooling2D((2, 2))(x)
        x = layers.Dropout(0.25)(x)
        
        x = layers.Conv2D(64, (3, 3), activation='relu', padding='same')(x)
        x = layers.BatchNormalization()(x)
        x = layers.MaxPooling2D((2, 2))(x)
        x = layers.Dropout(0.25)(x)
        
        x = layers.Conv2D(128, (3, 3), activation='relu', padding='same')(x)
        x = layers.BatchNormalization()(x)
        x = layers.MaxPooling2D((2, 2))(x)
        x = layers.Dropout(0.25)(x)
        
        x = layers.Conv2D(256, (3, 3), activation='relu', padding='same')(x)
        x = layers.BatchNormalization()(x)
        x = layers.MaxPooling2D((2, 2))(x)
        x = layers.Dropout(0.25)(x)
        
        x = layers.Conv2D(512, (3, 3), activation='relu', padding='same')(x)
        x = layers.BatchNormalization()(x)
        x = layers.GlobalAveragePooling2D()(x)
        
        # Dense layers
        x = layers.Dense(512, activation='relu')(x)
        x = layers.Dropout(0.5)(x)
        x = layers.Dense(256, activation='relu')(x)
        x = layers.Dropout(0.3)(x)
        
        # Embedding layer (L2 normalized)
        embeddings = layers.Dense(embedding_dim, name='embeddings')(x)
        embeddings = layers.Lambda(lambda x: tf.nn.l2_normalize(x, axis=1))(embeddings)
        
        model = models.Model(inputs=inputs, outputs=embeddings, name='facial_embedding_model')
        
        return model
    
    def build_fingerprint_model(self) -> Optional['keras.Model']:
        """Build fingerprint minutiae extraction model"""
        if not TF_AVAILABLE:
            return None
        
        config = self.MODEL_CONFIGS['fingerprint']
        input_shape = config['input_shape']
        embedding_dim = config['embedding_dim']
        
        inputs = layers.Input(shape=input_shape, name='fingerprint_input')
        
        # Enhanced edge detection layers
        x = layers.Conv2D(32, (5, 5), activation='relu', padding='same')(inputs)
        x = layers.BatchNormalization()(x)
        x = layers.Conv2D(32, (5, 5), activation='relu', padding='same')(x)
        x = layers.MaxPooling2D((2, 2))(x)
        
        x = layers.Conv2D(64, (3, 3), activation='relu', padding='same')(x)
        x = layers.BatchNormalization()(x)
        x = layers.Conv2D(64, (3, 3), activation='relu', padding='same')(x)
        x = layers.MaxPooling2D((2, 2))(x)
        
        x = layers.Conv2D(128, (3, 3), activation='relu', padding='same')(x)
        x = layers.BatchNormalization()(x)
        x = layers.GlobalAveragePooling2D()(x)
        
        x = layers.Dense(128, activation='relu')(x)
        x = layers.Dropout(0.4)(x)
        
        embeddings = layers.Dense(embedding_dim, name='embeddings')(x)
        embeddings = layers.Lambda(lambda x: tf.nn.l2_normalize(x, axis=1))(embeddings)
        
        model = models.Model(inputs=inputs, outputs=embeddings, name='fingerprint_embedding_model')
        
        return model
    
    def build_iris_model(self) -> Optional['keras.Model']:
        """Build iris recognition model (IrisCode-style)"""
        if not TF_AVAILABLE:
            return None
        
        config = self.MODEL_CONFIGS['iris']
        input_shape = config['input_shape']
        embedding_dim = config['embedding_dim']
        
        inputs = layers.Input(shape=input_shape, name='iris_input')
        
        # Gabor-like filter bank simulation
        x = layers.Conv2D(64, (1, 15), activation='relu', padding='same')(inputs)
        x = layers.Conv2D(64, (7, 1), activation='relu', padding='same')(x)
        x = layers.BatchNormalization()(x)
        x = layers.MaxPooling2D((2, 4))(x)
        
        x = layers.Conv2D(128, (3, 7), activation='relu', padding='same')(x)
        x = layers.BatchNormalization()(x)
        x = layers.MaxPooling2D((2, 4))(x)
        
        x = layers.Conv2D(256, (3, 5), activation='relu', padding='same')(x)
        x = layers.BatchNormalization()(x)
        x = layers.GlobalAveragePooling2D()(x)
        
        x = layers.Dense(512, activation='relu')(x)
        x = layers.Dropout(0.4)(x)
        
        embeddings = layers.Dense(embedding_dim, name='embeddings')(x)
        embeddings = layers.Lambda(lambda x: tf.nn.l2_normalize(x, axis=1))(embeddings)
        
        model = models.Model(inputs=inputs, outputs=embeddings, name='iris_embedding_model')
        
        return model
    
    # ==================== Triplet Loss for Metric Learning ====================
    
    def triplet_loss(self, margin: float = 0.2):
        """Triplet loss function for metric learning"""
        def loss(y_true, y_pred):
            # y_pred contains [anchor, positive, negative] embeddings stacked
            anchor, positive, negative = tf.split(y_pred, 3, axis=0)
            
            pos_dist = tf.reduce_sum(tf.square(anchor - positive), axis=1)
            neg_dist = tf.reduce_sum(tf.square(anchor - negative), axis=1)
            
            basic_loss = pos_dist - neg_dist + margin
            loss_value = tf.reduce_mean(tf.maximum(basic_loss, 0.0))
            
            return loss_value
        return loss
    
    def contrastive_loss(self, margin: float = 1.0):
        """Contrastive loss for siamese networks"""
        def loss(y_true, y_pred):
            square_pred = tf.square(y_pred)
            margin_square = tf.square(tf.maximum(margin - y_pred, 0))
            return tf.reduce_mean(y_true * square_pred + (1 - y_true) * margin_square)
        return loss
    
    # ==================== Data Preparation ====================
    
    def prepare_training_data(self, model_type: str, data_path: str = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Prepare training data for a biometric model"""
        config = self.MODEL_CONFIGS.get(model_type)
        if not config:
            raise ValueError(f"Unknown model type: {model_type}")
        
        input_shape = config['input_shape']
        data_path = data_path or str(self.data_dir / model_type)
        
        # Check if we have real training data
        if os.path.exists(data_path) and os.listdir(data_path):
            return self._load_real_data(data_path, input_shape)
        else:
            # Generate synthetic data for demonstration
            print(f"⚠ No training data found at {data_path}. Generating synthetic data...")
            return self._generate_synthetic_data(model_type, input_shape)
    
    def _load_real_data(self, data_path: str, input_shape: Tuple) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Load real training data from directory structure"""
        images = []
        labels = []
        
        data_path = Path(data_path)
        label_map = {}
        current_label = 0
        
        for person_dir in data_path.iterdir():
            if person_dir.is_dir():
                label_map[person_dir.name] = current_label
                for img_file in person_dir.glob('*'):
                    if img_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp']:
                        try:
                            if CV2_AVAILABLE:
                                img = cv2.imread(str(img_file))
                                if len(input_shape) == 3 and input_shape[2] == 1:
                                    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                                    img = cv2.resize(img, (input_shape[1], input_shape[0]))
                                    img = np.expand_dims(img, axis=-1)
                                else:
                                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                                    img = cv2.resize(img, (input_shape[1], input_shape[0]))
                                
                                images.append(img.astype(np.float32) / 255.0)
                                labels.append(current_label)
                        except Exception as e:
                            print(f"Error loading {img_file}: {e}")
                current_label += 1
        
        if len(images) == 0:
            return self._generate_synthetic_data(list(self.MODEL_CONFIGS.keys())[0], input_shape)
        
        X = np.array(images)
        y = np.array(labels)
        
        # Split data
        if SKLEARN_AVAILABLE:
            X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
        else:
            split_idx = int(len(X) * 0.8)
            X_train, X_val = X[:split_idx], X[split_idx:]
            y_train, y_val = y[:split_idx], y[split_idx:]
        
        return X_train, X_val, y_train, y_val
    
    def _generate_synthetic_data(self, model_type: str, input_shape: Tuple, 
                                  n_samples: int = 1000, n_classes: int = 50) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Generate synthetic training data for demonstration"""
        print(f"Generating {n_samples} synthetic samples for {model_type}...")
        
        # Generate class-specific patterns
        np.random.seed(42)
        class_patterns = [np.random.randn(*input_shape) * 0.3 for _ in range(n_classes)]
        
        X = []
        y = []
        
        samples_per_class = n_samples // n_classes
        
        for class_idx in range(n_classes):
            base_pattern = class_patterns[class_idx]
            for _ in range(samples_per_class):
                # Add noise to base pattern
                noise = np.random.randn(*input_shape) * 0.1
                sample = np.clip(base_pattern + noise + 0.5, 0, 1)
                X.append(sample.astype(np.float32))
                y.append(class_idx)
        
        X = np.array(X)
        y = np.array(y)
        
        # Shuffle
        indices = np.random.permutation(len(X))
        X = X[indices]
        y = y[indices]
        
        # Split
        split_idx = int(len(X) * 0.8)
        return X[:split_idx], X[split_idx:], y[:split_idx], y[split_idx:]
    
    # ==================== Training Functions ====================
    
    def train_model(self, model_type: str, epochs: int = None, 
                    data_path: str = None, callback: Callable = None) -> Dict:
        """Train a biometric model"""
        
        if not TF_AVAILABLE:
            return {
                'success': False,
                'error': 'TensorFlow is not available. Please install with: pip install tensorflow'
            }
        
        config = self.MODEL_CONFIGS.get(model_type)
        if not config:
            return {'success': False, 'error': f'Unknown model type: {model_type}'}
        
        job_id = str(uuid.uuid4())[:8]
        epochs = epochs or config['default_epochs']
        
        # Create training job
        self.db.create_training_job(job_id, model_type, epochs)
        self.training_jobs[job_id] = {
            'status': 'initializing',
            'model_type': model_type,
            'progress': 0,
            'current_epoch': 0,
            'total_epochs': epochs
        }
        
        # Start training in background thread
        thread = threading.Thread(
            target=self._train_worker,
            args=(job_id, model_type, epochs, data_path, callback)
        )
        thread.start()
        
        return {
            'success': True,
            'job_id': job_id,
            'message': f'Training started for {model_type} model',
            'epochs': epochs
        }
    
    def _train_worker(self, job_id: str, model_type: str, epochs: int, 
                      data_path: str, callback: Callable):
        """Background worker for model training"""
        try:
            self._update_job(job_id, status='preparing', progress=5)
            
            # Prepare data
            X_train, X_val, y_train, y_val = self.prepare_training_data(model_type, data_path)
            
            self._update_job(job_id, status='building', progress=10)
            
            # Build model
            if model_type == 'facial':
                model = self.build_facial_model()
            elif model_type == 'fingerprint':
                model = self.build_fingerprint_model()
            elif model_type == 'iris':
                model = self.build_iris_model()
            else:
                raise ValueError(f"Unknown model type: {model_type}")
            
            # Get number of classes
            n_classes = len(np.unique(y_train))
            
            # Add classification head for training
            classification_output = layers.Dense(n_classes, activation='softmax', name='classification')(model.output)
            training_model = models.Model(model.input, classification_output)
            
            # Compile
            training_model.compile(
                optimizer=optimizers.Adam(learning_rate=0.001),
                loss='sparse_categorical_crossentropy',
                metrics=['accuracy']
            )
            
            self._update_job(job_id, status='running', progress=15)
            
            # Training callbacks
            class ProgressCallback(callbacks.Callback):
                def __init__(self, trainer, job_id, total_epochs):
                    self.trainer = trainer
                    self.job_id = job_id
                    self.total_epochs = total_epochs
                
                def on_epoch_end(self, epoch, logs=None):
                    progress = 15 + (epoch + 1) / self.total_epochs * 80
                    self.trainer._update_job(
                        self.job_id,
                        current_epoch=epoch + 1,
                        progress=progress,
                        current_loss=logs.get('loss'),
                        current_accuracy=logs.get('accuracy')
                    )
            
            training_callbacks = [
                ProgressCallback(self, job_id, epochs),
                callbacks.EarlyStopping(patience=5, restore_best_weights=True),
                callbacks.ReduceLROnPlateau(factor=0.5, patience=3)
            ]
            
            # Train
            history = training_model.fit(
                X_train, y_train,
                validation_data=(X_val, y_val),
                epochs=epochs,
                batch_size=self.MODEL_CONFIGS[model_type]['batch_size'],
                callbacks=training_callbacks,
                verbose=1
            )
            
            # Evaluate
            val_loss, val_accuracy = training_model.evaluate(X_val, y_val, verbose=0)
            
            # Calculate additional metrics
            y_pred = np.argmax(training_model.predict(X_val), axis=1)
            metrics = {}
            if SKLEARN_AVAILABLE:
                metrics['precision'] = float(precision_score(y_val, y_pred, average='weighted'))
                metrics['recall'] = float(recall_score(y_val, y_pred, average='weighted'))
                metrics['f1_score'] = float(f1_score(y_val, y_pred, average='weighted'))
            
            # Save embedding model (without classification head)
            version = datetime.now().strftime('%Y%m%d_%H%M%S')
            model_filename = f"{model_type}_model_v{version}.h5"
            model_path = str(self.models_dir / model_filename)
            model.save(model_path)
            
            # Also save as latest
            latest_path = str(self.models_dir / f"{model_type}_model_latest.h5")
            model.save(latest_path)
            
            # Save to database
            self.db.save_model_metadata(
                model_name=f"{model_type}_embedding",
                model_type=model_type,
                version=version,
                architecture=self.MODEL_CONFIGS[model_type]['architecture'],
                accuracy=float(val_accuracy),
                training_samples=len(X_train),
                model_path=model_path,
                config=self.MODEL_CONFIGS[model_type],
                validation_samples=len(X_val),
                epochs_trained=len(history.history['loss']),
                **metrics
            )
            
            self._update_job(
                job_id,
                status='completed',
                progress=100,
                current_accuracy=float(val_accuracy)
            )
            
            print(f"✓ Training completed for {model_type} model")
            print(f"  Accuracy: {val_accuracy:.4f}")
            print(f"  Model saved to: {model_path}")
            
        except Exception as e:
            self._update_job(job_id, status='failed', error_message=str(e))
            print(f"✗ Training failed: {e}")
    
    def _update_job(self, job_id: str, **updates):
        """Update training job status"""
        if job_id in self.training_jobs:
            self.training_jobs[job_id].update(updates)
        self.db.update_training_job(job_id, **updates)
    
    def get_training_status(self, job_id: str) -> Optional[Dict]:
        """Get current training job status"""
        if job_id in self.training_jobs:
            return self.training_jobs[job_id]
        return self.db.get_training_job(job_id)
    
    # ==================== Model Loading ====================
    
    def load_model(self, model_type: str) -> Optional['keras.Model']:
        """Load a trained model"""
        if not TF_AVAILABLE:
            return None
        
        model_path = self.models_dir / f"{model_type}_model_latest.h5"
        if model_path.exists():
            try:
                model = models.load_model(str(model_path), compile=False)
                print(f"✓ Loaded {model_type} model from {model_path}")
                return model
            except Exception as e:
                print(f"⚠ Error loading model: {e}")
        
        return None
    
    def get_available_models(self) -> List[Dict]:
        """Get list of available trained models"""
        available = []
        
        for model_type in self.MODEL_CONFIGS.keys():
            model_path = self.models_dir / f"{model_type}_model_latest.h5"
            if model_path.exists():
                stat = model_path.stat()
                available.append({
                    'type': model_type,
                    'path': str(model_path),
                    'size_mb': stat.st_size / (1024 * 1024),
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        
        return available


# Global trainer instance
model_trainer = BiometricModelTrainer(
    models_dir=os.path.join(os.path.dirname(__file__), '..', 'models'),
    data_dir=os.path.join(os.path.dirname(__file__), '..', 'training_data')
)
