"""
Database Module for Biometric Identity System
Supports both SQLite (via SQLAlchemy) and MongoDB (via PyMongo)
"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, Any

# ==================== Dependencies ====================
try:
    from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker, relationship
    from sqlalchemy.exc import OperationalError
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    print("[WARN] SQLAlchemy not available.")

try:
    from pymongo import MongoClient
    from bson.objectid import ObjectId
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    print("[WARN] PyMongo not available.")

# ==================== Configuration ====================
DATABASE_TYPE = os.getenv('DATABASE_TYPE', 'sqlite')  # sqlite or mongodb
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///biometric_identity.db')
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/biometric_identity')

# ==================== SQL Models (Base) ====================
if SQLALCHEMY_AVAILABLE:
    Base = declarative_base()
    
    class Subject(Base):
        __tablename__ = 'subjects'
        id = Column(Integer, primary_key=True, index=True)
        subject_id = Column(String(64), unique=True, index=True, nullable=False)
        subject_code = Column(String(10), unique=True, index=True, nullable=True)
        name = Column(String(255), nullable=False)
        email = Column(String(255), nullable=True)
        biometric_type = Column(String(50), nullable=False)
        commitment_hash = Column(String(128), nullable=False)
        delta_storage_id = Column(String(128), nullable=True)
        blockchain_tx = Column(String(128), nullable=True)
        fingerprint_hash = Column(String(128), nullable=True)
        is_active = Column(Boolean, default=True)
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        authentications = relationship("AuthenticationLog", back_populates="subject")
        
        def to_dict(self):
            return {
                'id': self.id,
                'subject_id': self.subject_id,
                'subject_code': self.subject_code,
                'name': self.name,
                'email': self.email,
                'biometric_type': self.biometric_type,
                'commitment_hash': self.commitment_hash,
                'delta_storage_id': self.delta_storage_id,
                'fingerprint_hash': self.fingerprint_hash,
                'is_active': self.is_active,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'blockchain_tx': self.blockchain_tx
            }
    
    class AuthenticationLog(Base):
        __tablename__ = 'authentication_logs'
        id = Column(Integer, primary_key=True, index=True)
        subject_id = Column(String(64), ForeignKey('subjects.subject_id'), nullable=False)
        success = Column(Boolean, nullable=False)
        confidence = Column(Float, nullable=True)
        liveness_score = Column(Float, nullable=True)
        ip_address = Column(String(50), nullable=True)
        user_agent = Column(String(512), nullable=True)
        failure_reason = Column(String(255), nullable=True)
        created_at = Column(DateTime, default=datetime.utcnow)
        subject = relationship("Subject", back_populates="authentications")
        
        def to_dict(self):
            return {
                'id': self.id,
                'subject_id': self.subject_id,
                'success': self.success,
                'confidence': self.confidence,
                'liveness_score': self.liveness_score,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'failure_reason': self.failure_reason
            }
            
    class MLModel(Base):
        __tablename__ = 'ml_models'
        id = Column(Integer, primary_key=True, index=True)
        model_name = Column(String(100), nullable=False, index=True)
        model_type = Column(String(50), nullable=False)
        version = Column(String(20), nullable=False)
        architecture = Column(String(100), nullable=True)
        accuracy = Column(Float, nullable=True)
        precision_score = Column(Float, nullable=True)
        recall_score = Column(Float, nullable=True)
        f1_score = Column(Float, nullable=True)
        training_samples = Column(Integer, nullable=True)
        validation_samples = Column(Integer, nullable=True)
        epochs_trained = Column(Integer, nullable=True)
        model_path = Column(String(512), nullable=True)
        config = Column(Text, nullable=True)
        is_active = Column(Boolean, default=False)
        created_at = Column(DateTime, default=datetime.utcnow)
        
        def to_dict(self):
            return {
                'id': self.id,
                'model_name': self.model_name,
                'model_type': self.model_type,
                'version': self.version,
                'architecture': self.architecture,
                'accuracy': self.accuracy,
                'f1_score': self.f1_score,
                'training_samples': self.training_samples,
                'is_active': self.is_active,
                'created_at': self.created_at.isoformat() if self.created_at else None
            }

    class TrainingJob(Base):
        __tablename__ = 'training_jobs'
        id = Column(Integer, primary_key=True, index=True)
        job_id = Column(String(64), unique=True, index=True, nullable=False)
        model_type = Column(String(50), nullable=False)
        status = Column(String(20), default='pending')
        progress = Column(Float, default=0.0)
        current_epoch = Column(Integer, default=0)
        total_epochs = Column(Integer, nullable=True)
        current_loss = Column(Float, nullable=True)
        current_accuracy = Column(Float, nullable=True)
        error_message = Column(Text, nullable=True)
        started_at = Column(DateTime, nullable=True)
        completed_at = Column(DateTime, nullable=True)
        created_at = Column(DateTime, default=datetime.utcnow)
        
        def to_dict(self):
            return {
                'id': self.id,
                'job_id': self.job_id,
                'model_type': self.model_type,
                'status': self.status,
                'progress': self.progress,
                'current_epoch': self.current_epoch,
                'total_epochs': self.total_epochs,
                'current_loss': self.current_loss,
                'current_accuracy': self.current_accuracy,
                'error_message': self.error_message
            }
    
    class SystemConfig(Base):
        __tablename__ = 'system_config'
        id = Column(Integer, primary_key=True, index=True)
        key = Column(String(100), unique=True, nullable=False)
        value = Column(Text, nullable=True)
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ==================== Implementation: SQL ====================

class SqlDatabaseService:
    """SQLAlchemy Implementation"""
    def __init__(self):
        self.available = SQLALCHEMY_AVAILABLE
        if self.available:
            self.engine = create_engine(DATABASE_URL, echo=False)
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            try:
                Base.metadata.create_all(bind=self.engine)
            except OperationalError as e:
                # Gunicorn may start multiple workers; SQLite table creation can race during boot.
                if 'already exists' not in str(e).lower():
                    raise
            # Migrate: add fingerprint_hash column if missing (for existing databases)
            self._migrate_fingerprint_hash()
            print("[OK] SQLite initialized successfully")
        else:
            print("[WARN] SQLAlchemy not initialized")
    
    def _migrate_fingerprint_hash(self):
        """Add fingerprint_hash column to subjects table if it doesn't exist."""
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(self.engine)
            columns = [col['name'] for col in inspector.get_columns('subjects')]
            if 'fingerprint_hash' not in columns:
                with self.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE subjects ADD COLUMN fingerprint_hash VARCHAR(128)'))
                    conn.commit()
                print("[OK] Migration: Added fingerprint_hash column to subjects table")
        except Exception as e:
            print(f"[WARN] Migration check: {e}")
    
    def get_session(self):
        return self.SessionLocal() if self.available else None

    # ==================== Subject Operations ====================
    
    def create_subject(self, subject_id: str, name: str, biometric_type: str, 
                       commitment_hash: str, email: str = None,
                       delta_storage_id: str = None, subject_code: str = None,
                       fingerprint_hash: str = None) -> Dict[str, Any]:
        """Create a new enrolled subject"""
        if not self.available:
            return {'success': False, 'error': 'Database not available'}
            
        session = self.get_session()
        try:
            subject = Subject(
                subject_id=subject_id,
                subject_code=subject_code,
                name=name,
                email=email,
                biometric_type=biometric_type,
                commitment_hash=commitment_hash,
                delta_storage_id=delta_storage_id,
                fingerprint_hash=fingerprint_hash
            )
            session.add(subject)
            session.commit()
            session.refresh(subject)
            return {'success': True, 'subject': subject.to_dict()}
        except Exception as e:
            session.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            session.close()

    def get_subject(self, subject_id: str) -> Optional[Dict[str, Any]]:
        """Get a subject by ID or unique Subject Code"""
        if self.available:
            session = self.get_session()
            try:
                # Search by subject_id OR subject_code
                subject = session.query(Subject).filter(
                    (Subject.subject_id == subject_id) | (Subject.subject_code == subject_id)
                ).first()
                return subject.to_dict() if subject else None
            finally:
                session.close()

    def get_subject_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a subject by their name (fuzzy case-insensitive, ignores all spaces)"""
        if self.available:
            from sqlalchemy import func
            session = self.get_session()
            try:
                # Remove all spaces and lowercase both sides for maximum matches
                clean_name = "".join(name.split()).lower()
                subjects = session.query(Subject).all()
                for s in subjects:
                    if "".join(s.name.split()).lower() == clean_name:
                        return s.to_dict()
                return None
            finally:
                session.close()

    def get_all_subjects(self, limit=100, offset=0):
        if not self.available: return []
        session = self.get_session()
        try:
            subjects = session.query(Subject).filter(Subject.is_active == True)\
                .order_by(Subject.created_at.desc()).offset(offset).limit(limit).all()
            return [s.to_dict() for s in subjects]
        finally:
            session.close()
    
    def count_subjects(self):
        session = self.get_session()
        try: return session.query(Subject).filter(Subject.is_active == True).count()
        finally: session.close()

    def update_subject_blockchain_tx(self, subject_id, tx_hash):
        session = self.get_session()
        try:
            session.query(Subject).filter(Subject.subject_id == subject_id).update({'blockchain_tx': tx_hash})
            session.commit()
            return True
        except Exception:
            session.rollback()
            return False
        finally: session.close()
    
    # --- Auth Logs ---
    def log_authentication(self, subject_id, success, confidence=None, liveness_score=None, ip_address=None, user_agent=None, failure_reason=None):
        session = self.get_session()
        try:
            log = AuthenticationLog(
                subject_id=subject_id, success=success, confidence=confidence, 
                liveness_score=liveness_score, ip_address=ip_address, 
                user_agent=user_agent, failure_reason=failure_reason
            )
            session.add(log)
            session.commit()
            session.refresh(log)
            return {'success': True, 'log': log.to_dict()}
        except Exception as e: return {'success': False, 'error': str(e)}
        finally: session.close()

    def get_authentication_logs(self, subject_id=None, limit=50):
        session = self.get_session()
        try:
            query = session.query(AuthenticationLog)
            if subject_id: query = query.filter(AuthenticationLog.subject_id == subject_id)
            logs = query.order_by(AuthenticationLog.created_at.desc()).limit(limit).all()
            return [l.to_dict() for l in logs]
        finally: session.close()
    
    def count_authentications(self, success_only=False):
        session = self.get_session()
        try:
            query = session.query(AuthenticationLog)
            if success_only: query = query.filter(AuthenticationLog.success == True)
            return query.count()
        finally: session.close()

    # --- ML Models ---
    def save_model_metadata(self, model_name, model_type, version, architecture=None, accuracy=None, training_samples=None, model_path=None, config=None, **metrics):
        session = self.get_session()
        try:
            model = MLModel(
                model_name=model_name, model_type=model_type, version=version,
                architecture=architecture, accuracy=accuracy, training_samples=training_samples,
                model_path=model_path, config=json.dumps(config) if config else None,
                precision_score=metrics.get('precision'), recall_score=metrics.get('recall'),
                f1_score=metrics.get('f1_score'), validation_samples=metrics.get('validation_samples'),
                epochs_trained=metrics.get('epochs_trained')
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            return {'success': True, 'model': model.to_dict()}
        except Exception as e: return {'success': False, 'error': str(e)}
        finally: session.close()
        
    def get_active_model(self, model_type):
        session = self.get_session()
        try:
            model = session.query(MLModel).filter(MLModel.model_type == model_type, MLModel.is_active == True).first()
            return model.to_dict() if model else None
        finally: session.close()

    def activate_model(self, model_id):
        session = self.get_session()
        try:
            model = session.query(MLModel).filter(MLModel.id == model_id).first()
            if model:
                session.query(MLModel).filter(MLModel.model_type == model.model_type).update({'is_active': False})
                model.is_active = True
                session.commit()
                return True
            return False
        finally: session.close()

    def get_all_models(self, model_type=None):
        session = self.get_session()
        try:
            query = session.query(MLModel)
            if model_type: query = query.filter(MLModel.model_type == model_type)
            models = query.order_by(MLModel.created_at.desc()).all()
            return [m.to_dict() for m in models]
        finally: session.close()

    # --- Training Jobs ---
    def create_training_job(self, job_id, model_type, total_epochs=None):
        session = self.get_session()
        try:
            job = TrainingJob(job_id=job_id, model_type=model_type, total_epochs=total_epochs)
            session.add(job)
            session.commit()
            session.refresh(job)
            return {'success': True, 'job': job.to_dict()}
        except Exception as e: return {'success': False, 'error': str(e)}
        finally: session.close()

    def update_training_job(self, job_id, **updates):
        session = self.get_session()
        try:
            job = session.query(TrainingJob).filter(TrainingJob.job_id == job_id).first()
            if job:
                for k, v in updates.items():
                    if hasattr(job, k): setattr(job, k, v)
                if updates.get('status') == 'running' and not job.started_at:
                    job.started_at = datetime.utcnow()
                if updates.get('status') == 'completed':
                    job.completed_at = datetime.utcnow()
                session.commit()
                return True
            return False
        finally: session.close()

    def get_training_job(self, job_id):
        session = self.get_session()
        try:
            job = session.query(TrainingJob).filter(TrainingJob.job_id == job_id).first()
            return job.to_dict() if job else None
        finally: session.close()
        
    def get_statistics(self):
        return {
            'total_subjects': self.count_subjects(),
            'total_authentications': self.count_authentications(),
            'successful_authentications': self.count_authentications(success_only=True),
            'models_trained': len(self.get_all_models()),
            'database_available': self.available,
            'type': 'sqlite'
        }


# ==================== Implementation: MongoDB ====================

class MongoDatabaseService:
    """PyMongo Implementation"""
    def __init__(self):
        self.available = PYMONGO_AVAILABLE
        if self.available:
            try:
                self.client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
                self.db_name = MONGO_URI.rsplit('/', 1)[-1] if '/' in MONGO_URI else 'biometric_identity'
                self.db = self.client[self.db_name]
                # Test connection
                self.client.server_info()
                print(f"[OK] Connected to MongoDB at {MONGO_URI}")
                
                # Indexes
                self.db.subjects.create_index("subject_id", unique=True)
                self.db.subjects.create_index("created_at")
                self.db.authentication_logs.create_index("subject_id")
                self.db.authentication_logs.create_index("created_at")
                self.db.training_jobs.create_index("job_id", unique=True)
                
            except Exception as e:
                print(f"[WARN] Failed to connect to MongoDB: {e}")
                self.available = False
        else:
            print("[WARN] PyMongo not initialized")

    def _doc_to_dict(self, doc):
        if not doc: return None
        doc['id'] = str(doc['_id'])
        del doc['_id']
        # Convert datetimes
        for k, v in doc.items():
            if isinstance(v, datetime):
                doc[k] = v.isoformat()
        return doc

    # --- Subjects ---
    def create_subject(self, subject_id, name, biometric_type, commitment_hash, email=None, delta_storage_id=None, subject_code=None, fingerprint_hash=None):
        if not self.available: return {'success': False, 'error': 'DB unavailable'}
        try:
            now = datetime.utcnow()
            doc = {
                'subject_id': subject_id, 'subject_code': subject_code, 'name': name, 'email': email, 'biometric_type': biometric_type,
                'commitment_hash': commitment_hash, 'delta_storage_id': delta_storage_id,
                'fingerprint_hash': fingerprint_hash,
                'is_active': True, 'created_at': now, 'updated_at': now, 'blockchain_tx': None
            }
            res = self.db.subjects.insert_one(doc)
            doc['_id'] = res.inserted_id
            return {'success': True, 'subject': self._doc_to_dict(doc)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_subject(self, subject_id):
        if not self.available: return None
        # Try finding by subject_id or subject_code
        doc = self.db.subjects.find_one({
            '$or': [
                {'subject_id': subject_id},
                {'subject_code': subject_id}
            ]
        })
        return self._doc_to_dict(doc)

    def get_subject_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a subject by their name (fuzzy case-insensitive, ignores all spaces)"""
        if not self.available: return None
        # Retrieve all and check (for small datasets) or use a more complex regex
        cursor = self.db.subjects.find({})
        clean_name = "".join(name.split()).lower()
        for doc in cursor:
            if "".join(doc.get('name', '').split()).lower() == clean_name:
                return self._doc_to_dict(doc)
        return None

    def get_all_subjects(self, limit=100, offset=0):
        if not self.available: return []
        cursor = self.db.subjects.find({'is_active': True}).sort('created_at', -1).skip(offset).limit(limit)
        return [self._doc_to_dict(doc) for doc in cursor]

    def count_subjects(self):
        if not self.available: return 0
        return self.db.subjects.count_documents({'is_active': True})

    def update_subject_blockchain_tx(self, subject_id, tx_hash):
        if not self.available: return False
        res = self.db.subjects.update_one({'subject_id': subject_id}, {'$set': {'blockchain_tx': tx_hash}})
        return res.modified_count > 0

    # --- Auth Logs ---
    def log_authentication(self, subject_id, success, confidence=None, liveness_score=None, ip_address=None, user_agent=None, failure_reason=None):
        if not self.available: return {'success': False, 'error': 'DB unavailable'}
        try:
            doc = {
                'subject_id': subject_id, 'success': success, 'confidence': confidence,
                'liveness_score': liveness_score, 'ip_address': ip_address, 
                'user_agent': user_agent, 'failure_reason': failure_reason,
                'created_at': datetime.utcnow()
            }
            res = self.db.authentication_logs.insert_one(doc)
            doc['_id'] = res.inserted_id
            return {'success': True, 'log': self._doc_to_dict(doc)}
        except Exception as e: return {'success': False, 'error': str(e)}

    def get_authentication_logs(self, subject_id=None, limit=50):
        if not self.available: return []
        query = {'subject_id': subject_id} if subject_id else {}
        cursor = self.db.authentication_logs.find(query).sort('created_at', -1).limit(limit)
        return [self._doc_to_dict(doc) for doc in cursor]

    def count_authentications(self, success_only=False):
        if not self.available: return 0
        query = {'success': True} if success_only else {}
        return self.db.authentication_logs.count_documents(query)

    # --- ML Models ---
    def save_model_metadata(self, model_name, model_type, version, architecture=None, accuracy=None, training_samples=None, model_path=None, config=None, **metrics):
        if not self.available: return {'success': False, 'error': 'DB unavailable'}
        try:
            doc = {
                'model_name': model_name, 'model_type': model_type, 'version': version,
                'architecture': architecture, 'accuracy': accuracy, 'training_samples': training_samples,
                'model_path': model_path, 'config': config,  # Store as dict in Mongo
                'precision_score': metrics.get('precision'), 'recall_score': metrics.get('recall'),
                'f1_score': metrics.get('f1_score'), 'validation_samples': metrics.get('validation_samples'),
                'epochs_trained': metrics.get('epochs_trained'), 'is_active': False,
                'created_at': datetime.utcnow()
            }
            res = self.db.ml_models.insert_one(doc)
            doc['_id'] = res.inserted_id
            return {'success': True, 'model': self._doc_to_dict(doc)}
        except Exception as e: return {'success': False, 'error': str(e)}

    def get_active_model(self, model_type):
        if not self.available: return None
        doc = self.db.ml_models.find_one({'model_type': model_type, 'is_active': True})
        return self._doc_to_dict(doc)

    def activate_model(self, model_id):
        if not self.available: return False
        try:
            # Note: model_id in Mongo is string (ObjectId) via _doc_to_dict.
            # But frontend might pass string.
            oid = ObjectId(model_id)
            model = self.db.ml_models.find_one({'_id': oid})
            if model:
                self.db.ml_models.update_many({'model_type': model['model_type']}, {'$set': {'is_active': False}})
                self.db.ml_models.update_one({'_id': oid}, {'$set': {'is_active': True}})
                return True
            return False
        except Exception:
            return False

    def get_all_models(self, model_type=None):
        if not self.available: return []
        query = {'model_type': model_type} if model_type else {}
        cursor = self.db.ml_models.find(query).sort('created_at', -1)
        return [self._doc_to_dict(doc) for doc in cursor]

    # --- Training Jobs ---
    def create_training_job(self, job_id, model_type, total_epochs=None):
        if not self.available: return {'success': False, 'error': 'DB unavailable'}
        try:
            doc = {
                'job_id': job_id, 'model_type': model_type, 'status': 'pending',
                'progress': 0.0, 'current_epoch': 0, 'total_epochs': total_epochs,
                'current_loss': None, 'current_accuracy': None, 'error_message': None,
                'started_at': None, 'completed_at': None, 'created_at': datetime.utcnow()
            }
            res = self.db.training_jobs.insert_one(doc)
            doc['_id'] = res.inserted_id
            return {'success': True, 'job': self._doc_to_dict(doc)}
        except Exception as e: return {'success': False, 'error': str(e)}

    def update_training_job(self, job_id, **updates):
        if not self.available: return False
        try:
            if updates.get('status') == 'running':
                # Only set started_at if not set? 
                # Atomically tricky. Just set it if not exists.
                self.db.training_jobs.update_one(
                    {'job_id': job_id, 'started_at': None}, 
                    {'$set': {'started_at': datetime.utcnow()}}
                )
            if updates.get('status') == 'completed':
                updates['completed_at'] = datetime.utcnow()
            
            res = self.db.training_jobs.update_one({'job_id': job_id}, {'$set': updates})
            return res.modified_count > 0
        except Exception:
            return False

    def get_training_job(self, job_id):
        if not self.available: return None
        doc = self.db.training_jobs.find_one({'job_id': job_id})
        return self._doc_to_dict(doc)

    def get_statistics(self):
        return {
            'total_subjects': self.count_subjects(),
            'total_authentications': self.count_authentications(),
            'successful_authentications': self.count_authentications(success_only=True),
            'models_trained': len(self.get_all_models()),
            'database_available': self.available,
            'type': 'mongodb'
        }

# ==================== Factory ====================
print(f"Initializing Database Service. Type: {DATABASE_TYPE}")

if DATABASE_TYPE == 'mongodb':
    if PYMONGO_AVAILABLE:
        db_service = MongoDatabaseService()
    else:
        print("[WARN] DATABASE_TYPE is mongodb but pymongo is missing. Falling back to SQLite.")
        db_service = SqlDatabaseService()
else:
    db_service = SqlDatabaseService()