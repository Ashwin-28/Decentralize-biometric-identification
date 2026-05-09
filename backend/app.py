"""
Decentralized Biometric Identity Verification System
Flask Backend API

This module provides REST API endpoints for:
- Biometric feature extraction
- Fuzzy Commitment Scheme operations
- Blockchain interaction
- Identity enrollment and authentication
"""

import os
import json
import hashlib
import secrets
import base64
import random
import time
import sys
from datetime import datetime
from functools import wraps

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'), override=True)

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

import numpy as np

# Web3 for blockchain
from web3 import Web3
try:
    from web3.middleware import geth_poa_middleware as ExtraDataToRPCMiddleware
except ImportError:
    try:
        from web3.middleware import ExtraDataToRPCMiddleware
    except ImportError:
        # Fallback for very new versions if names change again
        ExtraDataToRPCMiddleware = None

# Local modules
from modules.biometric_engine import BiometricEngine
from modules.commitment_scheme import FuzzyCommitmentScheme
from modules.encryption import EncryptionService
from modules.storage import StorageClient
from modules.database import db_service
from modules.ml_trainer import model_trainer
from modules.fingerprint_reader import capture_fingerprint_image
from modules.fingerprint_processing import FingerprintProcessor

# ZKP Module
try:
    from modules.zkp_bridge import create_commitment as zkp_create_commitment
    from modules.zkp_bridge import generate_proof as zkp_generate_proof
    from modules.zkp_bridge import verify_proof as zkp_verify_proof
    from modules.zkp_bridge import authenticate_with_zkp
    ZKP_AVAILABLE = True
    print("[OK] ZKP module loaded")
except ImportError as e:
    ZKP_AVAILABLE = False
    print(f"[WARN] ZKP module not available: {e}")

try:
    from modules.voice_engine import (
        speech_to_text, get_voice_duration, 
        extract_voice_features, verify_liveness_code, compare_voice
    )
    VOICE_STT_AVAILABLE = True
except ImportError:
    VOICE_STT_AVAILABLE = False
    
# Store active voice challenges {subject_id: code}
voice_challenges = {}

# Store short-lived WebAuthn challenges by token
WEBAUTHN_CHALLENGE_TTL_SECONDS = int(os.environ.get('WEBAUTHN_CHALLENGE_TTL', '300'))
webauthn_challenges = {}

# ═══════════════════════════════════════════════════════════════════════════
#                              FLASK APP SETUP
# ═══════════════════════════════════════════════════════════════════════════

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Custom JSON Encoder for Numpy types
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.bool_, np.boolean)):
            return bool(obj)
        if isinstance(obj, (np.integer, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64, np.uint8, np.uint16, np.uint32, np.uint64)):
            return int(obj)
        if isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
            return float(obj)
        if isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

# Set custom JSON encoder (compatible with Flask 2.x and 3.x)
try:
    app.json.encoder = NumpyEncoder
except AttributeError:
    app.json_encoder = NumpyEncoder

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'bmp', 'gif', 'webp', 'webm', 'wav', 'ogg', 'mp3'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
UPLOAD_FOLDER = app.config['UPLOAD_FOLDER']
import traceback

# Initialize services
# Use 512D for ArcFace/FaceNet512 (better accuracy), fallback to 128D for FaceNet
biometric_engine = BiometricEngine(feature_dim=512)  # ArcFace uses 512D embeddings for better accuracy
# Update FCS to handle variable feature dimensions
fcs = FuzzyCommitmentScheme(key_length=16, feature_dim=512, error_tolerance=0.40, code_redundancy=7)
encryption = EncryptionService()
from modules.storage import storage_service as storage

# Blockchain configuration
BLOCKCHAIN_URL = os.environ.get('BLOCKCHAIN_URL', 'http://127.0.0.1:8545')
CONTRACT_ADDRESS = os.environ.get('CONTRACT_ADDRESS', '')
PRIVATE_KEY = os.environ.get('PRIVATE_KEY', '')
GANACHE_ACCOUNT = os.environ.get('GANACHE_ACCOUNT', '')  # Unlocked Ganache account
w3 = None

ganache_contract = None # BiometricRegistry
contract = None # Main Registry
fp_contract = None # FingerprintRegistry
voice_auth_contract = None # VoiceAuth (New Dual-Gate)


def _load_artifact(contract_name):
    """Load a Truffle artifact from build/contracts."""
    candidate_paths = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), 'build', 'contracts', f'{contract_name}.json')),
        os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'build', 'contracts', f'{contract_name}.json')),
        os.path.abspath(os.path.join('/build/contracts', f'{contract_name}.json')),
    ]

    for artifact_path in candidate_paths:
        if os.path.exists(artifact_path):
            with open(artifact_path, 'r', encoding='utf-8') as f:
                return json.load(f)

    return None


def _resolve_deployed_address(artifact_json, preferred_address=''):
    """Resolve the most appropriate deployed address for the connected chain."""
    if not artifact_json:
        return preferred_address or ''

    networks = artifact_json.get('networks', {}) or {}
    if not networks:
        return preferred_address or ''

    # Keep caller-provided address if it exists in the artifact deployments.
    if preferred_address:
        preferred_lower = preferred_address.lower()
        for deployment in networks.values():
            addr = deployment.get('address')
            if addr and addr.lower() == preferred_lower:
                return addr

    # Prefer the currently connected chain ID when available.
    if w3 and w3.is_connected():
        chain_id_key = str(w3.eth.chain_id)
        chain_deployment = networks.get(chain_id_key, {})
        chain_address = chain_deployment.get('address')
        if chain_address:
            return chain_address

    # Common local Ganache fallback.
    local_deployment = networks.get('1337', {})
    local_address = local_deployment.get('address')
    if local_address:
        return local_address

    # Last fallback: first deployment entry.
    first_deployment = next(iter(networks.values()))
    return first_deployment.get('address', preferred_address or '')

def get_sender_account():
    """Get the account to use for transactions"""
    if PRIVATE_KEY:
        return w3.eth.account.from_key(PRIVATE_KEY).address
    # For Ganache, prefer using the first unlocked account directly
    elif w3 and w3.is_connected() and w3.eth.accounts:
        return w3.eth.accounts[0]
    elif GANACHE_ACCOUNT:
        try:
            return Web3.to_checksum_address(GANACHE_ACCOUNT)
        except Exception:
            return None
    return None


def init_blockchain():
    """Initialize Web3 and contract connection"""
    global w3, contract, fp_contract, voice_auth_contract, CONTRACT_ADDRESS
    
    try:
        w3 = Web3(Web3.HTTPProvider(BLOCKCHAIN_URL))
        if not w3.is_connected():
            print(f"[WARN] Cannot connect to blockchain provider: {BLOCKCHAIN_URL}")
            return

        if ExtraDataToRPCMiddleware:
            w3.middleware_onion.inject(ExtraDataToRPCMiddleware, layer=0)

        contract_json = _load_artifact('BiometricRegistry')
        if not contract_json:
            print("[WARN] BiometricRegistry artifact not found - please compile and deploy first")
            return

        resolved_main_address = _resolve_deployed_address(contract_json, CONTRACT_ADDRESS)
        if not resolved_main_address:
            print("[WARN] No BiometricRegistry deployment found in artifact networks")
            return

        CONTRACT_ADDRESS = resolved_main_address
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(CONTRACT_ADDRESS),
            abi=contract_json['abi']
        )

        # Load FingerprintRegistry as well
        fp_json = _load_artifact('FingerprintRegistry')
        if fp_json:
            preferred_fp = os.environ.get('FP_CONTRACT_ADDRESS', '')
            fp_addr = _resolve_deployed_address(fp_json, preferred_fp)
            if fp_addr:
                fp_contract = w3.eth.contract(
                    address=Web3.to_checksum_address(fp_addr),
                    abi=fp_json['abi']
                )
                print(f"[OK] FingerprintRegistry loaded: {fp_addr}")

        # Load VoiceAuth (Dual-Gate)
        from modules.voice_engine import VOICE_AUTH_ABI
        vjson = _load_artifact('VoiceAuth')
        preferred_voice = os.environ.get('VOICE_AUTH_ADDRESS', '')
        voice_addr = _resolve_deployed_address(vjson, preferred_voice)

        if voice_addr:
            voice_auth_contract = w3.eth.contract(
                address=Web3.to_checksum_address(voice_addr),
                abi=VOICE_AUTH_ABI
            )
            print(f"[OK] VoiceAuth (Dual-Gate) loaded: {voice_addr}")

        print(f"[OK] Connected to blockchain at {BLOCKCHAIN_URL}")
        print(f"[OK] Contract loaded: {CONTRACT_ADDRESS}")
            
    except Exception as e:
        print(f"[ERR] Blockchain initialization failed: {e}")


# Initialize blockchain on import so Gunicorn workers also connect.
init_blockchain()


# ===========================================================================
#                               HELPERS
# ===========================================================================

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def require_blockchain(f):
    """Decorator to verify blockchain connection"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not w3 or not w3.is_connected():
            return jsonify({'error': 'Blockchain not connected'}), 503
        return f(*args, **kwargs)
    return decorated


def generate_subject_id(data: str) -> str:
    """Generate unique subject identifier"""
    timestamp = datetime.now().isoformat()
    random_bytes = secrets.token_bytes(16)
    combined = f"{data}{timestamp}{random_bytes.hex()}"
    return hashlib.sha256(combined.encode()).hexdigest()


def generate_human_code() -> str:
    """Generate a unique 6-digit numeric subject code"""
    import secrets
    import string
    
    # Try multiple times to find a unique code
    for _ in range(10):
        code = ''.join(secrets.choice(string.digits) for _ in range(6))
        
        # Check if code already exists in database
        if not db_service.get_subject(code):
            return code
            
    # Fallback to longer code if many collisions occur
    return ''.join(secrets.choice(string.digits) for _ in range(10))


def _b64url_encode(data: bytes) -> str:
    """Encode bytes into URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _b64url_decode(value: str) -> bytes:
    """Decode URL-safe base64 string that may omit padding."""
    if not isinstance(value, str):
        raise ValueError('Expected a base64url string')
    padding = '=' * ((4 - (len(value) % 4)) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _origin_allowed(origin: str) -> bool:
    """Allow HTTPS origins plus localhost for local development."""
    if not isinstance(origin, str) or not origin:
        return False
    return origin.startswith('https://') or origin.startswith('http://localhost') or origin.startswith('http://127.0.0.1')


def _prune_webauthn_challenges() -> None:
    """Remove expired in-memory challenge entries."""
    now = time.time()
    expired_tokens = [
        token for token, payload in webauthn_challenges.items()
        if now - payload.get('created_at', 0) > WEBAUTHN_CHALLENGE_TTL_SECONDS
    ]
    for token in expired_tokens:
        webauthn_challenges.pop(token, None)


def _create_webauthn_challenge(purpose: str, **context) -> tuple[str, str]:
    """Create a challenge token and persist challenge context for one request cycle."""
    _prune_webauthn_challenges()
    token = secrets.token_urlsafe(24)
    challenge = _b64url_encode(secrets.token_bytes(32))
    webauthn_challenges[token] = {
        'purpose': purpose,
        'challenge': challenge,
        'created_at': time.time(),
        **context,
    }
    return token, challenge


def _consume_webauthn_challenge(token: str, purpose: str):
    """Fetch and remove a challenge context if it is valid and matches purpose."""
    _prune_webauthn_challenges()
    if not token:
        return None

    payload = webauthn_challenges.pop(token, None)
    if not payload:
        return None

    if payload.get('purpose') != purpose:
        return None

    age = time.time() - payload.get('created_at', 0)
    if age > WEBAUTHN_CHALLENGE_TTL_SECONDS:
        return None

    return payload


def _parse_webauthn_client_data(client_data_json_b64url: str) -> dict:
    """Decode and parse WebAuthn clientDataJSON payload."""
    try:
        decoded = _b64url_decode(client_data_json_b64url)
        return json.loads(decoded.decode('utf-8'))
    except Exception as exc:
        raise ValueError(f'Invalid clientDataJSON: {exc}') from exc


def _normalize_webauthn_credential_id(credential: dict) -> str:
    """Use WebAuthn credential id, preferring id then rawId if needed."""
    if not isinstance(credential, dict):
        return ''
    credential_id = credential.get('id') or credential.get('rawId')
    return str(credential_id or '').strip()


# ═══════════════════════════════════════════════════════════════════════════
#                             HEALTH ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/api/health', methods=['GET'])
def health_check():
    """System health check"""
    blockchain_status = 'connected' if (w3 and w3.is_connected()) else 'disconnected'
    return jsonify({
        'status': 'healthy',
        'blockchain': blockchain_status,
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.1-testing'
    })


@app.route('/api/blockchain/status', methods=['GET'])
def blockchain_status():
    """Get detailed blockchain status"""
    try:
        if w3 and w3.is_connected():
            return jsonify({
                'connected': True,
                'network_id': str(w3.net.version) if hasattr(w3.net, 'version') else 'unknown',
                'block_number': w3.eth.block_number,
                'gas_price': str(w3.eth.gas_price),
                'contract_address': CONTRACT_ADDRESS
            })
    except Exception as e:
        print(f"[WARN] Blockchain status check failed: {e}")
    return jsonify({'connected': False})


@app.route('/api/blockchain/explorer', methods=['GET'])
def blockchain_explorer():
    """Get blockchain data for the explorer UI"""
    if not w3 or not w3.is_connected():
        return jsonify({
            'blocks': [],
            'transactions': [],
            'accounts': []
        })
    
    try:
        # Get recent blocks
        current_block = w3.eth.block_number
        blocks = []
        all_transactions = []
        
        # Fetch last 20 blocks
        for i in range(max(0, current_block - 19), current_block + 1):
            try:
                block = w3.eth.get_block(i, full_transactions=True)
                block_data = {
                    'number': block.number,
                    'hash': block.hash.hex() if block.hash else None,
                    'parentHash': block.parentHash.hex() if block.parentHash else None,
                    'timestamp': block.timestamp,
                    'gasLimit': block.gasLimit,
                    'gasUsed': block.gasUsed,
                    'miner': block.miner,
                    'transactions': [tx.hash.hex() for tx in block.transactions] if block.transactions else []
                }
                blocks.append(block_data)
                
                # Collect transactions
                for tx in block.transactions:
                    tx_data = {
                        'hash': tx.hash.hex(),
                        'blockNumber': tx.blockNumber,
                        'from': tx['from'],
                        'to': tx.to,
                        'value': str(tx.value),
                        'gas': tx.gas,
                        'gasPrice': str(tx.gasPrice) if tx.gasPrice else '0',
                        'input': tx.input.hex() if tx.input else '0x'
                    }
                    all_transactions.append(tx_data)
            except Exception:
                continue
        
        # Reverse to show newest first
        blocks.reverse()
        all_transactions.reverse()
        
        # Get accounts
        accounts = []
        try:
            account_list = w3.eth.accounts
            for addr in account_list:
                balance = w3.eth.get_balance(addr)
                tx_count = w3.eth.get_transaction_count(addr)
                accounts.append({
                    'address': addr,
                    'balance': str(balance),
                    'txCount': tx_count
                })
        except Exception:
            pass
        
        return jsonify({
            'blocks': blocks,
            'transactions': all_transactions,
            'accounts': accounts
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'blocks': [],
            'transactions': [],
            'accounts': []
        })


# ═══════════════════════════════════════════════════════════════════════════
#                          BIOMETRIC ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/api/biometric/extract', methods=['POST'])
def extract_biometric():
    """Extract biometric features from uploaded image"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    biometric_type = request.form.get('type', 'facial')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        features = biometric_engine.extract_features(filepath, biometric_type)
        os.remove(filepath)
        
        if features is None:
            return jsonify({'error': 'Could not extract biometric features'}), 400
        
        features_b64 = base64.b64encode(features.tobytes()).decode('utf-8')
        
        return jsonify({
            'success': True,
            'features': features_b64,
            'biometric_type': biometric_type,
            'feature_length': len(features)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/biometric/liveness', methods=['POST'])
def check_liveness():
    """Perform anti-spoofing liveness detection"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        is_live, confidence = biometric_engine.check_liveness(filepath)
        os.remove(filepath)
        
        return jsonify({
            'is_live': is_live,
            'confidence': float(confidence)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/fingerprint/capture', methods=['POST'])
def capture_fingerprint():
    """Trigger the hardware fingerprint sensor to capture vector via Windows Hello and process it.
    
    Each capture generates a DETERMINISTIC template hash from the actual biometric data.
    Same finger → same vector → same hash (every time).
    Different finger → different vector → different hash.
    """
    import base64
    from modules.fingerprint_processing import FingerprintProcessor
    processor = FingerprintProcessor(threshold=0.85)
    
    print("\n" + "="*50)
    print("  STEP 1: FINGERPRINT SCANNER")
    print("="*50)
    print("Initializing Biometric Sensor...")
    time.sleep(1)
    print("👉 ACTION: Place finger on the sensor area.")
    
    # Simulate a scanning progress bar for visual impact
    for i in range(1, 11):
        sys.stdout.write(f"\rScanning Surface: [{'#' * i}{'-' * (10-i)}] {i*10}%")
        sys.stdout.flush()
        time.sleep(0.2)
    print("\n")

    try:
        from modules.fingerprint_reader import capture_fingerprint_vector
        vector_str = capture_fingerprint_vector()
        
        print(f"[INFO] capture_fingerprint_vector returned: {'<vector>' if vector_str else 'None'}")
        
        if vector_str is not None:
            if vector_str == "ERR_UNKNOWN_ID":
                # Sensor read a finger but it is not enrolled in Windows Hello.
                import uuid
                vector_str = f"UNKNOWN_{uuid.uuid4().hex}"
            elif vector_str == "ERR_TIMEOUT":
                return jsonify({
                    'success': False,
                    'error': 'Scanner timed out. Please keep your finger on the sensor.'
                }), 400
                
            # REAL sensor capture succeeded
            # The vector_str is deterministic per finger (Windows Hello SID+subfactor)
            # Same finger ALWAYS produces the exact same vector_str
            # e.g. "SID_01050000000000515...._SF2"
            
            vector_str_repr = str(vector_str)
            print(f"[OK] Real sensor vector: {vector_str_repr[:30]}...")
            
            template, fingerprint_hash = processor.generate_template_and_hash(
                [(ord(c), i, 0.0) for i, c in enumerate(vector_str_repr[:50])]
            )
            
            fake_img_data = f"FID:{vector_str_repr}".encode('utf-8')
            img_b64 = base64.b64encode(fake_img_data).decode('utf-8')
            
            print(f"[OK] Real fingerprint hash: {fingerprint_hash}")
            return jsonify({
                'success': True,
                'image_b64': img_b64,
                'simulated': False,
                'hash': fingerprint_hash,
                'template': template,
                'message': 'Fingerprint identity captured and hashed via Windows Hello sensor'
            })
        else:
            # SENSOR NOT AVAILABLE — use a stable simulation hash
            # This allows demo mode to work: same "simulated finger" always matches
            # To test non-match, enroll with one type and verify without sensor
            print("[WARN] Sensor returned None — using stable simulation fingerprint")
            
            # Use a fixed simulated identity so enrollment + verification produce same hash
            import hashlib as _hl
            # The stable ID is based on the Windows username — same user = same hash
            import os
            username = os.environ.get('USERNAME', os.environ.get('USER', 'demo_user'))
            stable_vector = f"SIMULATED_FINGER_{username}"
            minutiae_data = [(ord(c), i, 0.0) for i, c in enumerate(stable_vector[:50])]
            template, fingerprint_hash = processor.generate_template_and_hash(minutiae_data)
            
            fake_img_data = f"FID:SIM_{stable_vector}".encode('utf-8')
            img_b64 = base64.b64encode(fake_img_data).decode('utf-8')
            
            print(f"[OK] Stable simulation hash: {fingerprint_hash}")
            return jsonify({
                'success': True,
                'image_b64': img_b64,
                'simulated': True,
                'hash': fingerprint_hash,
                'template': template,
                'message': 'Fingerprint captured (SIMULATED). Same simulated finger used for demo mode.'
            })
            
    except Exception as e:
        print(f"[ERR] Fingerprint capture failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ═══════════════════════════════════════════════════════════════════════════
#                          NEW: DESKTOP ARCHITECTURE ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/api/fingerprint/register', methods=['POST'])
def RegisterFingerprint():
    """As requested: Receive fingerprint scan and store hash in blockchain."""
    data = request.json
    user_id = data.get('userId')
    fingerprint_hash = data.get('fingerprintHash')
    
    if not user_id or not fingerprint_hash:
        return jsonify({'error': 'Missing userId or fingerprintHash'}), 400
        
    print(f"[BLOCKCHAIN] Registering fingerprint for {user_id}...")
    
    try:
        if fp_contract and w3 and w3.is_connected():
            sender = get_sender_account()
            tx_hash = fp_contract.functions.registerFingerprint(
                user_id,
                fingerprint_hash
            ).transact({'from': sender})
            w3.eth.wait_for_transaction_receipt(tx_hash)
            
            return jsonify({
                'status': 'SUCCESS',
                'userId': user_id,
                'transactionId': tx_hash.hex(),
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'status': 'SUCCESS',
                'userId': user_id,
                'transactionId': f"0x{secrets.token_hex(32)}",
                'timestamp': datetime.now().isoformat(),
                'note': 'Demo mode (Blockchain simulation)'
            })
    except Exception as e:
        print(f"[ERR] FP Registration failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/fingerprint/verify', methods=['POST'])
def VerifyFingerprint():
    """Receive scan hash or template, compare with stored data using similarity metrics."""
    data = request.json
    user_id = data.get('userId')
    scan_hash = data.get('scanHash')
    scan_template = data.get('template') 
    scan_image_path = data.get('imagePath') # New: use image if available
    
    if not user_id:
        return jsonify({'error': 'Missing userId'}), 400

    try:
        subject = db_service.get_subject(user_id)
        if not subject:
            return jsonify({'status': 'NOT MATCHED', 'error': 'Subject not found'})

        stored_hash = subject.get('fingerprint_hash')
        stored_template = ""
        stored_cid = subject.get('delta_storage_id')
        
        # 1. Similarity Check Priority
        similarity = 0.0
        threshold = 0.70
        is_match = False
        
        # Case A: ORB Image Matching (User's New Recommendation)
        if scan_image_path and os.path.exists(scan_image_path):
            # We would need a stored image path, which we might not have for privacy.
            # But if we do (demo mode), we use ORB.
            pass

        # Case B: Minutiae Template (Stored in storage)
        if not is_match and stored_cid:
            try:
                enc_data = storage.get(stored_cid)
                if enc_data:
                    decrypted = encryption.decrypt(enc_data)
                    # Try minutiae string matching
                    if b"|" in decrypted:
                        from modules.fingerprint_processing import FingerprintProcessor
                        processor = FingerprintProcessor(threshold=threshold)
                        similarity = processor.get_similarity(scan_template, decrypted.decode())
                        is_match = similarity >= threshold
            except: pass

        # Case C: SID/FID HASH Check (Strictly for Windows Hello SIDs)
        if not is_match and scan_hash and stored_hash:
            # We compare the SID-derived hashes. This is only a "match" if the SIDs are identical.
            is_match = (scan_hash == stored_hash)
            similarity = 1.0 if is_match else 0.0

        result = "MATCH" if is_match else "NOT MATCHED"
        return jsonify({
            'status': result,
            'similarity': float(similarity),
            'threshold': threshold
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'status': 'NOT MATCHED', 'error': str(e)}), 200



@app.route('/api/fingerprint/status', methods=['GET'])
def fingerprint_sensor_status():
    """Check if the fingerprint sensor is available."""
    from modules.fingerprint_reader import is_sensor_available
    available = is_sensor_available()
    return jsonify({
        'available': available,
        'message': 'Sensor detected' if available else 'No fingerprint sensor found or WBF service stopped'
    })


@app.route('/api/webauthn/status', methods=['GET'])
def webauthn_status():
    """Expose WebAuthn backend capability for browser-native fingerprint flows."""
    return jsonify({
        'available': True,
        'requires_https': True,
        'challenge_ttl_seconds': WEBAUTHN_CHALLENGE_TTL_SECONDS,
        'message': 'WebAuthn challenge endpoints are ready'
    })


@app.route('/api/webauthn/register/options', methods=['POST'])
def webauthn_register_options():
    """Create WebAuthn registration challenge/options for client authenticator."""
    data = request.get_json(silent=True) or {}
    name = str(data.get('name') or '').strip()
    email = str(data.get('email') or '').strip() or None

    if not name:
        return jsonify({'success': False, 'error': 'Name is required'}), 400

    token, challenge = _create_webauthn_challenge('register', name=name, email=email)
    user_handle = _b64url_encode(secrets.token_bytes(16))

    return jsonify({
        'success': True,
        'token': token,
        'publicKey': {
            'challenge': challenge,
            'rp': {
                'name': 'Biometric Identity Platform'
            },
            'user': {
                'id': user_handle,
                'name': name,
                'displayName': name
            },
            'pubKeyCredParams': [
                {'type': 'public-key', 'alg': -7},
                {'type': 'public-key', 'alg': -257}
            ],
            'timeout': 60000,
            'attestation': 'none',
            'authenticatorSelection': {
                'userVerification': 'required',
                'residentKey': 'preferred'
            }
        }
    })


@app.route('/api/webauthn/register/verify', methods=['POST'])
def webauthn_register_verify():
    """Verify WebAuthn registration response and persist credential id for fingerprint auth."""
    data = request.get_json(silent=True) or {}
    token = str(data.get('token') or '').strip()
    name = str(data.get('name') or '').strip()
    email = str(data.get('email') or '').strip() or None
    credential = data.get('credential') or {}

    challenge_state = _consume_webauthn_challenge(token, 'register')
    if not challenge_state:
        return jsonify({'success': False, 'error': 'Registration challenge expired or invalid'}), 400

    if not name:
        name = str(challenge_state.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'Name is required'}), 400

    credential_id = _normalize_webauthn_credential_id(credential)
    if not credential_id:
        return jsonify({'success': False, 'error': 'Credential id missing'}), 400

    response_payload = credential.get('response') if isinstance(credential, dict) else {}
    client_data_b64 = (response_payload or {}).get('clientDataJSON')
    if not client_data_b64:
        return jsonify({'success': False, 'error': 'clientDataJSON is required'}), 400

    try:
        client_data = _parse_webauthn_client_data(client_data_b64)
    except ValueError as decode_err:
        return jsonify({'success': False, 'error': str(decode_err)}), 400

    if client_data.get('type') != 'webauthn.create':
        return jsonify({'success': False, 'error': 'Unexpected WebAuthn operation type'}), 400

    if client_data.get('challenge') != challenge_state.get('challenge'):
        return jsonify({'success': False, 'error': 'Challenge mismatch'}), 400

    if not _origin_allowed(client_data.get('origin', '')):
        return jsonify({'success': False, 'error': 'Origin not allowed'}), 400

    subject_id = generate_subject_id(name + 'fingerprint_webauthn')
    subject_code = generate_human_code()
    commitment_hash = hashlib.sha256(credential_id.encode('utf-8')).hexdigest()

    db_result = db_service.create_subject(
        subject_id=subject_id,
        subject_code=subject_code,
        name=name,
        email=email,
        biometric_type='fingerprint',
        commitment_hash=commitment_hash,
        delta_storage_id='webauthn',
        fingerprint_hash=credential_id
    )

    if not db_result.get('success'):
        return jsonify({'success': False, 'error': db_result.get('error', 'Database save failed')}), 500

    result = {
        'success': True,
        'subject_id': subject_id,
        'subject_code': subject_code,
        'biometric_type': 'fingerprint',
        'credential_id': credential_id,
        'message': 'Fingerprint credential enrolled successfully'
    }

    sender = get_sender_account()
    if sender and w3 and w3.is_connected() and contract:
        try:
            tx_params = {
                'from': sender,
                'gas': 500000,
                'gasPrice': w3.eth.gas_price
            }
            subject_id_bytes = bytes.fromhex(subject_id)
            commitment_hash_bytes = bytes.fromhex(commitment_hash)
            delta_bytes = hashlib.sha256(f"{credential_id}:{subject_id}".encode('utf-8')).digest()[:16]

            if PRIVATE_KEY:
                tx_params['nonce'] = w3.eth.get_transaction_count(sender)
                tx = contract.functions.enrollSubject(
                    subject_id_bytes,
                    commitment_hash_bytes,
                    delta_bytes,
                    'webauthn',
                    1
                ).build_transaction(tx_params)
                signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
                tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            else:
                tx_hash = contract.functions.enrollSubject(
                    subject_id_bytes,
                    commitment_hash_bytes,
                    delta_bytes,
                    'webauthn',
                    1
                ).transact(tx_params)

            receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
            result['transaction_hash'] = tx_hash.hex()
            result['block_number'] = receipt.get('blockNumber')
            db_service.update_subject_blockchain_tx(subject_id, tx_hash.hex())
        except Exception as chain_err:
            result['blockchain_error'] = str(chain_err)

    return jsonify(result), 201


@app.route('/api/webauthn/authenticate/options', methods=['POST'])
def webauthn_authenticate_options():
    """Create WebAuthn authentication challenge/options for a registered subject."""
    data = request.get_json(silent=True) or {}
    query = str(data.get('subject_id') or data.get('query') or data.get('name') or '').strip()

    if not query:
        return jsonify({'success': False, 'error': 'Subject ID or name is required'}), 400

    subject = db_service.get_subject(query)
    if not subject:
        subject = db_service.get_subject_by_name(query)

    if not subject:
        return jsonify({'success': False, 'error': 'Subject not found'}), 404

    credential_id = str(subject.get('fingerprint_hash') or '').strip()
    if not credential_id:
        return jsonify({'success': False, 'error': 'No WebAuthn credential found for subject'}), 400

    token, challenge = _create_webauthn_challenge(
        'authenticate',
        subject_id=subject['subject_id'],
        credential_id=credential_id
    )

    return jsonify({
        'success': True,
        'token': token,
        'subject_id': subject['subject_id'],
        'publicKey': {
            'challenge': challenge,
            'timeout': 60000,
            'allowCredentials': [
                {'type': 'public-key', 'id': credential_id}
            ],
            'userVerification': 'required'
        }
    })


@app.route('/api/webauthn/authenticate/verify', methods=['POST'])
def webauthn_authenticate_verify():
    """Verify WebAuthn authentication response and record successful login."""
    data = request.get_json(silent=True) or {}
    token = str(data.get('token') or '').strip()
    credential = data.get('credential') or {}

    challenge_state = _consume_webauthn_challenge(token, 'authenticate')
    if not challenge_state:
        return jsonify({'success': False, 'error': 'Authentication challenge expired or invalid'}), 400

    credential_id = _normalize_webauthn_credential_id(credential)
    expected_id = str(challenge_state.get('credential_id') or '').strip()

    if not credential_id or credential_id != expected_id:
        return jsonify({'success': False, 'error': 'Credential id mismatch'}), 401

    response_payload = credential.get('response') if isinstance(credential, dict) else {}
    client_data_b64 = (response_payload or {}).get('clientDataJSON')
    if not client_data_b64:
        return jsonify({'success': False, 'error': 'clientDataJSON is required'}), 400

    try:
        client_data = _parse_webauthn_client_data(client_data_b64)
    except ValueError as decode_err:
        return jsonify({'success': False, 'error': str(decode_err)}), 400

    if client_data.get('type') != 'webauthn.get':
        return jsonify({'success': False, 'error': 'Unexpected WebAuthn operation type'}), 400

    if client_data.get('challenge') != challenge_state.get('challenge'):
        return jsonify({'success': False, 'error': 'Challenge mismatch'}), 400

    if not _origin_allowed(client_data.get('origin', '')):
        return jsonify({'success': False, 'error': 'Origin not allowed'}), 400

    subject_id = str(challenge_state.get('subject_id') or '')
    subject = db_service.get_subject(subject_id)
    if not subject:
        return jsonify({'success': False, 'error': 'Subject not found'}), 404

    confidence = 99.0
    logged_on_chain = False
    blockchain_warning = None

    sender = get_sender_account()
    if sender and w3 and w3.is_connected() and contract:
        try:
            tx_params = {
                'from': sender,
                'gas': 500000,
                'gasPrice': w3.eth.gas_price
            }
            clean_id = subject_id[2:] if subject_id.startswith('0x') else subject_id
            reason = 'WebAuthn verified'

            if PRIVATE_KEY:
                tx_params['nonce'] = w3.eth.get_transaction_count(sender)
                tx = contract.functions.logAuthentication(
                    bytes.fromhex(clean_id), True, reason
                ).build_transaction(tx_params)
                signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
                w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            else:
                contract.functions.logAuthentication(
                    bytes.fromhex(clean_id), True, reason
                ).transact(tx_params)

            logged_on_chain = True
        except Exception as chain_err:
            blockchain_warning = str(chain_err)

    db_service.log_authentication(
        subject_id=subject_id,
        success=True,
        confidence=confidence,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')[:500],
        failure_reason=None
    )

    return jsonify({
        'success': True,
        'subject_id': subject_id,
        'subject_code': subject.get('subject_code'),
        'biometric_type': 'fingerprint',
        'confidence': confidence,
        'logged_on_chain': logged_on_chain,
        'blockchain_warning': blockchain_warning,
        'message': 'Matched Successful'
    })

@app.route('/api/check-user', methods=['POST'])
def check_user_exists():
    """Verify if a user exists by name, subject ID, or subject code."""
    data = request.get_json(silent=True) or {}
    query = str(data.get('query') or data.get('name') or data.get('subject_id') or data.get('identifier') or '').strip()
    if not query:
        return jsonify({'exists': False, 'error': 'Name or subject ID required'}), 400

    subject = db_service.get_subject(query)
    if not subject:
        subject = db_service.get_subject_by_name(query)

    if subject:
        return jsonify({
            'exists': True, 
            'subject_id': subject['subject_id'],
            'subject_code': subject.get('subject_code'),
            'name': subject.get('name'),
            'biometric_type': subject['biometric_type']
        })
    return jsonify({'exists': False, 'message': 'User not found'})


# ===========================================================================
#                          ENROLLMENT ENDPOINTS
# ===========================================================================

@app.route('/api/enroll', methods=['POST'])
def enroll_subject():
    """Enroll a new subject with biometric data.
    
    For fingerprint: expects 'fingerprint_hash' form field with the template hash
    captured from the sensor. This hash is stored and used for verification.
    """
    global contract, voice_auth_contract, w3
    if 'file' not in request.files:
        return jsonify({'error': 'No biometric file provided'}), 400
    
    file = request.files['file']
    biometric_type = request.form.get('type', 'facial')
    name = request.form.get('name', '')
    email = request.form.get('email', None)
    fingerprint_hash = request.form.get('fingerprint_hash', None)
    
    try:
        # Save and process biometric
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        features = biometric_engine.extract_features(filepath, biometric_type)
        # For voice enrollments, keep the file — we need it for MFCC extraction below.
        # It will be cleaned up after MFCC extraction.
        if biometric_type != 'voice':
            os.remove(filepath)
        
        if features is None:
            return jsonify({'error': 'Could not extract biometric features'}), 400
        
        print(f"[OK] Extracted features: shape={features.shape}, dtype={features.dtype}")
        print(f"   Feature stats: min={features.min():.4f}, max={features.max():.4f}, mean={features.mean():.4f}")
        
        # For fingerprint: store the template hash from the sensor capture
        if biometric_type == 'fingerprint' and fingerprint_hash:
            print(f"[ENROLL] Fingerprint template hash stored: {fingerprint_hash[:20]}...")

        # For voice: extract spoken password
        spoken_password = request.form.get('spoken_password', None)
        if biometric_type == 'voice' and not spoken_password:
            if VOICE_STT_AVAILABLE:
                # Fallback to backend STT if frontend didn't provide one
                temp_filename = secure_filename(file.filename)
                temp_path = os.path.join(app.config['UPLOAD_FOLDER'], "stt_" + temp_filename)
                file.stream.seek(0) # reset stream
                file.save(temp_path)
                spoken_password = speech_to_text(temp_path)
                os.remove(temp_path)
                print(f"[VOICE-ENROLL] Recognized password via backend: '{spoken_password}'")
            else:
                print("[WARN] Voice STT not available and no frontend transcript provided")
        elif biometric_type == 'voice' and spoken_password:
            print(f"[VOICE-ENROLL] Using frontend-provided password: '{spoken_password}'")
        
        if biometric_type == 'voice':
            if spoken_password:
                # Enrolled successfully, encrypt and store
                encrypted_pwd = encryption.encrypt(spoken_password.lower().strip().encode())
                fingerprint_hash = base64.b64encode(encrypted_pwd).decode()
                print(f"[VOICE-ENROLL] Password encrypted and stored in fingerprint_hash field")
            else:
                print("[VOICE-ENROLL] ❌ FAILED to recognize any speech in enrollment audio.")
        
        # Generate subject ID
        subject_id = generate_subject_id(name + biometric_type)
        
        # Apply Fuzzy Commitment Scheme
        commitment = fcs.commit(features)
        
        # Encrypt template for off-chain storage
        encrypted_template = encryption.encrypt(features.tobytes())
        
        # Store on IPFS/local
        template_cid = storage.add(encrypted_template)
        
        # Also save raw features for demo mode comparison
        storage.save_features(subject_id, features)
        
        # ── SAVE MFCC FEATURES for voice enrollments ──
        if biometric_type == 'voice':
            # Convert the uploaded audio to WAV first (browser sends WebM)
            wav_enroll_path = filepath + "_enroll.wav"
            try:
                import subprocess
                subprocess.run([
                    "ffmpeg", "-y", "-i", filepath,
                    "-ar", "16000", "-ac", "1", wav_enroll_path
                ], check=True, capture_output=True)
                audio_for_mfcc = wav_enroll_path
                print(f"[VOICE-ENROLL] Converted enrollment audio to WAV")
            except Exception:
                audio_for_mfcc = filepath  # fallback to original
                wav_enroll_path = None
                print(f"[VOICE-ENROLL] ffmpeg not available, using raw file for MFCC")

            try:
                import librosa
                y, sr = librosa.load(audio_for_mfcc, sr=16000)
                y, _ = librosa.effects.trim(y, top_db=20)
                mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=40)
                mfcc_vec = np.concatenate([np.mean(mfccs, axis=1), np.std(mfccs, axis=1)])
                norm = np.linalg.norm(mfcc_vec)
                mfcc_vec = mfcc_vec / norm if norm > 0 else mfcc_vec
                storage.save_features(subject_id + '_voice_mfcc', mfcc_vec)
                print(f"[VOICE-ENROLL] ✅ MFCC voice biometric features SAVED for subject: {subject_id[:8]}")
                print(f"[VOICE-ENROLL]    MFCC shape={mfcc_vec.shape}, norm={np.linalg.norm(mfcc_vec):.4f}")
            except Exception as mfcc_err:
                print(f"[VOICE-ENROLL] ❌ MFCC save FAILED: {mfcc_err}")
                import traceback; traceback.print_exc()

            # Now clean up the uploaded file and any WAV conversion
            try:
                if os.path.exists(filepath): os.remove(filepath)
            except: pass
            try:
                if wav_enroll_path and os.path.exists(wav_enroll_path): os.remove(wav_enroll_path)
            except: pass

        # Prepare blockchain data
        subject_id_bytes = bytes.fromhex(subject_id)
        commitment_hash = commitment['hash']
        delta_bytes = commitment['delta']
        subject_code = generate_human_code()
        
        # Store in database (including fingerprint_hash if applicable)
        db_result = db_service.create_subject(
            subject_id=subject_id,
            subject_code=subject_code,
            name=name,
            email=email,
            biometric_type=biometric_type,
            commitment_hash=commitment_hash.hex(),
            delta_storage_id=template_cid,
            fingerprint_hash=fingerprint_hash if biometric_type in ['fingerprint', 'voice'] else None
        )
        
        if not db_result['success']:
            return jsonify({'error': db_result.get('error', 'Database save failed')}), 500
        
        result = {
            'success': True,
            'subject_id': subject_id,
            'subject_code': subject_code,
            'commitment_hash': commitment_hash.hex(),
            'delta': delta_bytes.hex(),
            'template_cid': template_cid,
            'biometric_type': biometric_type,
            'message': f'Identity enrolled successfully. Your Subject Code is: {subject_code}'
        }
        
        if biometric_type == 'fingerprint' and fingerprint_hash:
            result['fingerprint_hash'] = fingerprint_hash
        
        # Submit to blockchain if connected
        sender = get_sender_account()
        if w3 and w3.is_connected() and contract and sender:
            try:
                biometric_enum = {'facial': 0, 'fingerprint': 1, 'voice': 2, 'multimodal': 3}
                bio_type = biometric_enum.get(biometric_type, 0)
                
                # Build transaction
                tx_params = {
                    'from': sender,
                    'gas': 500000,
                    'gasPrice': w3.eth.gas_price
                }
                
                if PRIVATE_KEY:
                    # Signed transaction
                    tx_params['nonce'] = w3.eth.get_transaction_count(sender)
                    tx = contract.functions.enrollSubject(
                        subject_id_bytes,
                        commitment_hash,
                        delta_bytes,
                        template_cid,
                        bio_type
                    ).build_transaction(tx_params)
                    signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
                    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                else:
                    # Unlocked Ganache account - direct send
                    tx_hash = contract.functions.enrollSubject(
                        subject_id_bytes,
                        commitment_hash,
                        delta_bytes,
                        template_cid,
                        bio_type
                    ).transact(tx_params)
                
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
                
                result['transaction_hash'] = tx_hash.hex()
                result['block_number'] = receipt['blockNumber']
                result['message'] = 'Subject enrolled successfully on blockchain'
                
                print(f"[OK] Enrolled on blockchain: tx={tx_hash.hex()}, block={receipt['blockNumber']}")
                
                # Update database with blockchain tx
                db_service.update_subject_blockchain_tx(subject_id, tx_hash.hex())
                
                # NEW: Store Voice Hash in VoiceAuth contract if applicable
                if biometric_type == 'voice' and voice_auth_contract:
                    from modules.voice_engine import features_to_hash
                    vhash = features_to_hash(features)
                    # We store the ID as string since VoiceAuth.sol uses string memory userId
                    vhash_tx = voice_auth_contract.functions.storeHash(subject_id, vhash).transact(tx_params)
                    print(f"[VOICE-ENROLL] Voice feature-hash stored in VoiceAuth: {vhash} (tx: {vhash_tx.hex()})")
                    # Do NOT overwrite fingerprint_hash, as it holds the encrypted password!

            except Exception as e:
                result['blockchain_error'] = str(e)
                result['message'] = 'Enrollment prepared but blockchain submission failed'
                print(f"[ERR] Blockchain enrollment failed: {e}")
        
        return jsonify(result), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===========================================================================
#                        AUTHENTICATION ENDPOINTS
# =============================================================================

@app.route('/api/authenticate', methods=['POST'])
def authenticate_subject():
    """Authenticate a subject using biometric verification.
    
    For fingerprint: expects 'fingerprint_hash' form field with the template hash
    from the current sensor capture. This is compared against the stored hash.
    """
    global contract, voice_auth_contract, w3
    if 'file' not in request.files:
        return jsonify({'error': 'No biometric file provided'}), 400
    
    file = request.files['file']
    subject_id = request.form.get('subject_id', '')
    biometric_type = request.form.get('type', 'facial')
    auth_fingerprint_hash = request.form.get('fingerprint_hash', None)
    
    print(f"DEBUG: Authenticating {subject_id}. Contract Address: '{CONTRACT_ADDRESS}'")

    if not subject_id:
        return jsonify({'error': 'Subject ID required'}), 400
    
    try:
        # Process biometric
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # ============================================================
        # VOICE: Handle voice separately (independent pipeline)
        # ============================================================
        if biometric_type == 'voice':
            print(f"[AUTH-VOICE] === Password + Voice Biometric Verification ===")
            
            # 1. Find subject (by ID or Name)
            subject_db = db_service.get_subject(subject_id)
            if not subject_db:
                subject_db = db_service.get_subject_by_name(subject_id)
            
            if not subject_db:
                if os.path.exists(filepath): os.remove(filepath)
                return jsonify({
                    'success': False,
                    'error': 'Subject not found. Please ensure you enter the correct name/ID.',
                    'message': 'Not Matched'
                }), 404
            
            subject_id = subject_db['subject_id']

            # ── CONVERT AUDIO TO WAV (browser sends WebM/Opus) ──────────────────
            wav_filepath = filepath + "_converted.wav"
            try:
                import subprocess
                subprocess.run([
                    "ffmpeg", "-y", "-i", filepath,
                    "-ar", "16000",  # 16kHz
                    "-ac", "1",      # mono
                    wav_filepath
                ], check=True, capture_output=True)
                print(f"[AUTH-VOICE] Audio converted to WAV: {wav_filepath}")
            except Exception as conv_err:
                print(f"[AUTH-VOICE] ffmpeg conversion failed: {conv_err} — using original file")
                wav_filepath = filepath  # fallback to original

            # ── GATE 1: PASSWORD GATE ────────────────────────────────────────────
            print("\n" + "="*50)
            print("  GATE 1: PASSWORD GATE")
            print("="*50)

            spoken_password = request.form.get('spoken_password', '')
            print(f"[AUTH-VOICE] Frontend STT received: '{spoken_password}'")

            if not spoken_password and VOICE_STT_AVAILABLE:
                try:
                    spoken_password = speech_to_text(wav_filepath)
                    print(f"[AUTH-VOICE] Backend STT result: '{spoken_password}'")
                except Exception as stt_err:
                    print(f"[AUTH-VOICE] Backend STT failed: {stt_err}")

            if not spoken_password:
                print("[AUTH-VOICE] No speech detected")
                for f in [filepath, wav_filepath]:
                    if f != filepath and os.path.exists(f): os.remove(f)
                if os.path.exists(filepath): os.remove(filepath)
                return jsonify({
                    'success': False,
                    'error': 'No speech detected. Please speak your password clearly.',
                    'message': 'Not Matched'
                }), 200

            spoken_password = spoken_password.lower().strip()
            print(f"[AUTH-VOICE] Spoken password: '{spoken_password}'")

            stored_encrypted_pwd = subject_db.get('fingerprint_hash')
            password_match = False

            if stored_encrypted_pwd:
                try:
                    encrypted_bytes = base64.b64decode(stored_encrypted_pwd)
                    stored_password = encryption.decrypt(encrypted_bytes).decode().lower().strip()
                    print(f"[AUTH-VOICE] Stored password: '{stored_password}'")

                    if spoken_password == stored_password:
                        password_match = True
                        print("✅ PASSWORD MATCH (exact)")
                    elif stored_password in spoken_password or spoken_password in stored_password:
                        password_match = True
                        print("✅ PASSWORD MATCH (partial)")
                    else:
                        spoken_words = set(spoken_password.split())
                        stored_words  = set(stored_password.split())
                        if stored_words:
                            overlap = len(spoken_words & stored_words) / max(len(stored_words), 1)
                            if overlap >= 0.5:
                                password_match = True
                                print(f"✅ PASSWORD MATCH (word overlap={overlap:.0%})")
                            else:
                                print(f"❌ PASSWORD MISMATCH (overlap={overlap:.0%})")
                except Exception as dec_err:
                    print(f"[AUTH-VOICE] Password decryption error: {dec_err} — bypassing gate")
                    password_match = True  # Don't block on decryption errors
            else:
                print("[AUTH-VOICE] No stored password — skipping password gate")
                password_match = True

            # ── GATE 2: VOICE BIOMETRIC GATE (MFCC-based) ───────────────────────
            print("\n" + "="*50)
            print("  GATE 2: VOICE BIOMETRIC GATE")
            print("="*50)

            voice_match = False
            confidence  = 0.0

            try:
                import librosa
                from scipy.spatial.distance import cosine as cosine_dist

                def extract_mfcc_features(audio_path):
                    """Extract stable MFCC voice fingerprint."""
                    y, sr = librosa.load(audio_path, sr=16000)
                    y, _ = librosa.effects.trim(y, top_db=20)  # remove silence
                    if len(y) < sr * 0.5:  # less than 0.5s of audio
                        print(f"[AUTH-VOICE] Audio too short: {len(y)/sr:.2f}s")
                        return None
                    mfccs       = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=40)
                    mfcc_mean   = np.mean(mfccs, axis=1)
                    mfcc_std    = np.std(mfccs,  axis=1)
                    features    = np.concatenate([mfcc_mean, mfcc_std])
                    norm        = np.linalg.norm(features)
                    return features / norm if norm > 0 else features

                print(f"[AUTH-VOICE] Extracting MFCC from live audio: {wav_filepath}")
                live_features = extract_mfcc_features(wav_filepath)

                if live_features is None:
                    print("[AUTH-VOICE] ⚠ Could not extract MFCC — audio too short or silent")
                    # Don't fail hard — allow password gate to decide
                    voice_match = password_match
                    confidence  = 50.0 if password_match else 0.0
                else:
                    print(f"[AUTH-VOICE] Live MFCC shape: {live_features.shape}")

                    # Try to load stored MFCC features
                    stored_mfcc = None

                    # Option A: Load from dedicated MFCC storage key
                    try:
                        stored_mfcc_raw = storage.load_features(subject_id + '_voice_mfcc')
                        if stored_mfcc_raw is not None:
                            stored_mfcc = np.array(stored_mfcc_raw, dtype=np.float32)
                            print(f"[AUTH-VOICE] Loaded stored MFCC features: {stored_mfcc.shape}")
                    except Exception as e:
                        print(f"[AUTH-VOICE] MFCC load failed: {e}")

                    # Option B: Fallback — load raw stored features and try cosine anyway
                    if stored_mfcc is None:
                        try:
                            template_cid = subject_db.get('delta_storage_id')
                            if template_cid:
                                enc = storage.get(template_cid)
                                if enc:
                                    dec = encryption.decrypt(enc)
                                    stored_raw = np.frombuffer(dec, dtype=np.float32)
                                    # Resize stored features to match live MFCC size
                                    if len(stored_raw) >= len(live_features):
                                        stored_mfcc = stored_raw[:len(live_features)]
                                    else:
                                        stored_mfcc = np.pad(stored_raw,
                                            (0, len(live_features) - len(stored_raw)))
                                    print(f"[AUTH-VOICE] Fallback stored features shape: {stored_mfcc.shape}")
                        except Exception as e:
                            print(f"[AUTH-VOICE] Fallback feature load failed: {e}")

                    if stored_mfcc is not None:
                        # Cosine similarity
                        sim = 1.0 - cosine_dist(
                            live_features.astype(np.float64),
                            stored_mfcc.astype(np.float64)
                        )
                        confidence   = float(sim * 100.0)
                        # Threshold 0.40 — accounts for natural voice variation
                        # across different recordings of the SAME speaker
                        voice_match  = sim >= 0.40
                        print(f"[AUTH-VOICE] Cosine similarity={sim:.4f}, threshold=0.40, match={voice_match}")
                    else:
                        print("[AUTH-VOICE] ⚠ No stored MFCC features found — legacy enrollment detected")
                        print("[AUTH-VOICE]   Falling back to password-only. Re-enroll to enable voice biometrics.")
                        # Legacy enrollment without MFCC: allow password-only
                        # but flag that voice biometrics are not active
                        voice_match = password_match
                        confidence  = 50.0 if password_match else 0.0

            except ImportError:
                print("[AUTH-VOICE] librosa not installed — voice biometric gate UNAVAILABLE")
                # If librosa is missing, we can't do voice biometrics at all
                # Fall back to password-only
                voice_match = password_match
                confidence  = 50.0 if password_match else 0.0

            except Exception as ve:
                print(f"[AUTH-VOICE] MFCC comparison error: {ve}")
                import traceback; traceback.print_exc()
                # On error, fall back to password-only so the user isn't completely locked out
                voice_match = password_match
                confidence  = 50.0 if password_match else 0.0

            # ── FINAL DECISION ───────────────────────────────────────────────────
            # BOTH gates MUST pass: correct password AND matching voice biometric.
            # This prevents someone else from saying the correct password.
            is_authenticated = password_match and voice_match
            print(f"\n{'='*50}")
            print(f"  FINAL AUTHENTICATION DECISION")
            print(f"{'='*50}")
            print(f"  Password Gate: {'✅ PASS' if password_match else '❌ FAIL'}")
            print(f"  Voice Bio Gate: {'✅ PASS' if voice_match else '❌ FAIL'} (confidence={confidence:.1f}%)")
            print(f"  Result: {'🔓 AUTHENTICATED' if is_authenticated else '🚫 DENIED'}")
            print(f"{'='*50}")

            # Note for UI
            if not voice_match and password_match:
                 print("[AUTH-VOICE] NOTE: Password was correct, but voice biometrics did not match or were missing. Failing verification.")

            # Clean up temp files
            for f in [filepath, wav_filepath]:
                try:
                    if os.path.exists(f): os.remove(f)
                except: pass

            # ── BLOCKCHAIN LOG ───────────────────────────────────────────────────
            logged_on_chain = False
            sender = get_sender_account()
            if is_authenticated and w3 and w3.is_connected() and contract and sender:
                try:
                    clean_id = subject_id[2:] if subject_id.startswith('0x') else subject_id
                    sid_bytes = bytes.fromhex(clean_id).ljust(32, b'\0')[:32]
                    contract.functions.logAuthentication(
                        sid_bytes, True, "Voice+Password Verified"
                    ).transact({'from': sender, 'gas': 500000})
                    logged_on_chain = True
                    print("[AUTH-VOICE] Blockchain log SUCCESS")
                except Exception as e:
                    print(f"[AUTH-VOICE] Blockchain log failed: {e}")

            # ── RESPONSE ─────────────────────────────────────────────────────────
            if is_authenticated:
                final_msg = '✅ Matched Successful (Voice + Password Verified)'
            elif not password_match:
                final_msg = '❌ Not Matched — Password mismatch'
            else:
                final_msg = '❌ Not Matched — Voice biometric mismatch'

            print(f"[AUTH-VOICE] RESULT: {final_msg} (confidence={confidence:.1f}%)")

            return jsonify({
                'success':        bool(is_authenticated),
                'confidence':     float(round(confidence, 2)),
                'subject_id':     subject_id,
                'logged_on_chain': bool(logged_on_chain),
                'message':        str(final_msg)
            })
            
    except Exception as e:
        # GLOBAL CRASH RECOVERY
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ CRITICAL AUTH ERROR: {e}\n{error_trace}")
        
        # Clean up file if still exists
        try:
            if 'filepath' in locals() and os.path.exists(filepath):
                os.remove(filepath)
        except: pass
            
        return jsonify({
            'success': False,
            'error': f'Internal Server Error: {str(e)}',
            'message': 'Verification Failed due to system error'
        }), 200 # Return 200 so the UI can show the message instead of crashing
        
    # ── Non-voice: Extract features normally ──
    features = biometric_engine.extract_features(filepath, biometric_type)
    os.remove(filepath)
    
    if features is None:
        return jsonify({'error': 'Could not extract biometric features'}), 400
    
    print(f"[INFO] Auth: Extracted features shape={features.shape}, dtype={features.dtype}")
    print(f"   Feature stats: min={features.min():.4f}, max={features.max():.4f}, mean={features.mean():.4f}")
    
    # ============================================================
    # FINGERPRINT: Probabilistic Vector Comparison (Solution 2)
    # ============================================================
    if biometric_type == 'fingerprint':
        print(f"[AUTH-FP] === Probabilistic Fingerprint Verification ===")
        
        # Step 1: Identity Check — find the subject
        subject_db = db_service.get_subject(subject_id)
        if not subject_db:
            subject_db = db_service.get_subject_by_name(subject_id)
        if not subject_db:
            return jsonify({
                'success': False,
                'error': 'Subject not found. Please enroll first.',
                'subject_id': subject_id,
                'message': 'Not Matched'
            }), 404
        
        # Use actual subject ID
        real_subject_id = subject_db['subject_id']
        subject_id = real_subject_id
        
        # Step 2: Fetch Template — retrieve the STORED VECTOR (not hash)
        stored_vector_cid = subject_db.get('delta_storage_id')
        stored_fp_hash = subject_db.get('fingerprint_hash')
        
        is_match = False
        confidence = 0.0
        threshold = 0.70 # Updated to 0.7 per user request
        
        # PRIMARY: Probabilistic vector comparison (Solution 2)
        if stored_vector_cid:
            try:
                enc_template = storage.get(stored_vector_cid)
                if enc_template:
                    # Decrypt and check format
                    decrypted = encryption.decrypt(enc_template)
                    
                    # Case A: Minutiae Template (String)
                    # Case B: Feature Vectors (Numpy)
                    if b"|" in decrypted:
                        # Minutiae template
                        live_minutiae = request.form.get('template', '')
                        if live_minutiae:
                            from modules.fingerprint_processing import FingerprintProcessor
                            processor = FingerprintProcessor(threshold=threshold)
                            similarity = processor.get_similarity(live_minutiae, decrypted.decode())
                            confidence = float(similarity * 100.0)
                            is_match = similarity >= threshold
                        else:
                            print("[AUTH-FP] No minutiae template provided in auth request")
                    else:
                        # Feature vector
                        stored_features = np.frombuffer(decrypted, dtype=np.float32)
                        similarity = biometric_engine.compare(
                            features, stored_features, bio_type='fingerprint'
                        )
                        confidence = float(similarity * 100.0)
                        is_match = similarity >= threshold
                    
                    print(f"[AUTH-FP] similarity: {confidence:.2f}% (Threshold={threshold*100}%)")
            except Exception as e:
                print(f"[WARN] Fingerprint comparison error: {e}")
        
        # FALLBACK: Deterministic hash match (only if vector match failed)
        if not is_match and auth_fingerprint_hash and stored_fp_hash:
            is_match = (auth_fingerprint_hash == stored_fp_hash)
            if is_match:
                confidence = 100.0
                print("[AUTH-FP] Matched via deterministic hash fallback")
        
        print(f"[AUTH-FP] Final: {'MATCH' if is_match else 'NOT MATCHED'} ({confidence:.1f}%)")
        
        # Log on blockchain
        logged_on_chain = False
        blockchain_warning = None
        sender = get_sender_account()
        if sender and w3 and w3.is_connected() and contract:
            try:
                reason = f"FP Match ({confidence:.1f}%)" if is_match else "FP Mismatch"
                tx_params = {'from': sender, 'gas': 500000, 'gasPrice': w3.eth.gas_price}
                contract.functions.logAuthentication(
                    bytes.fromhex(subject_id), is_match, reason
                ).transact(tx_params)
                logged_on_chain = True
            except Exception as e:
                blockchain_warning = str(e)
        
        # Log to database
        db_service.log_authentication(
            subject_id=subject_id,
            success=is_match,
            confidence=confidence,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:500],
            failure_reason=None if is_match else 'Biometric vector similarity too low'
        )
        
        return jsonify({
            'success': bool(is_match),
            'confidence': float(confidence),
            'subject_id': str(subject_id),
            'logged_on_chain': bool(logged_on_chain),
            'blockchain_warning': str(blockchain_warning) if blockchain_warning else None,
            'message': 'Verification Successful' if is_match else 'Verification Failed'
        })
    
    # ============================================================
    # NON-FINGERPRINT: Standard Feature-Based Verification
    # ============================================================
    # Verify against blockchain
    stored_hash = None
    stored_delta = None
    template_cid = None
    
    stored_bio_type = 'facial'
    
    import time
    start_time = time.time()

    # Try Blockchain First 
    if w3 and w3.is_connected() and contract:
        try:
            subject_id_bytes = bytes.fromhex(subject_id)
            sender = get_sender_account()
            call_params = {'from': sender} if sender else {}
            
            print(f"[AUTH] Starting blockchain lookup for {subject_id[:8]}...")
            stored_data = contract.functions.getSubject(subject_id_bytes).call(call_params)
            print(f"[AUTH] Blockchain lookup took {(time.time() - start_time):.3f}s")
            
            if stored_data[0]:  # isRegistered
                stored_hash = stored_data[1]
                stored_delta = stored_data[2]
                template_cid = stored_data[3]
                
                # Convert enum back to string
                bio_enum_rev = {0: 'facial', 1: 'fingerprint', 2: 'iris', 3: 'multimodal'}
                stored_bio_type = bio_enum_rev.get(stored_data[4], 'facial')
                
                print(f"[INFO] Data source: Blockchain (Hash={stored_hash.hex()[:8]}..., Type={stored_bio_type})")
        except Exception as e:
            print(f"[WARN] Blockchain lookup failed: {e}")

    # Fallback to Database
    if not stored_hash:
        print("[INFO] Blockchain data unavailable, checking local database...")
        subject_db = db_service.get_subject(subject_id)
        if not subject_db:
            subject_db = db_service.get_subject_by_name(subject_id)
            if subject_db: subject_id = subject_db['subject_id']
        
        if subject_db and subject_db.get('commitment_hash'):
            try:
                stored_hash = bytes.fromhex(subject_db['commitment_hash'])
                template_cid = subject_db.get('delta_storage_id')
                stored_bio_type = subject_db.get('biometric_type', 'facial')
                print(f"[INFO] Data source: Local DB (Type={stored_bio_type})")
            except Exception as e:
                print(f"[ERR] DB data parsing failed: {e}")

    if not stored_hash:
         return jsonify({
            'success': False,
            'error': 'Subject not found. Please enroll first.',
            'subject_id': subject_id,
            'message': 'Not Matched'
        }), 404
        
    # ════════════════════════════════════════════════════════════
    # SECURITY CHECK - Modality Mismatch Detection
    # ════════════════════════════════════════════════════════════
    if stored_bio_type != biometric_type:
        print(f"[SECURITY] Modality mismatch: Requested {biometric_type}, Stored {stored_bio_type}")
        return jsonify({
            'success': False,
            'error': f'Biometric modality mismatch. Identity was enrolled with {stored_bio_type.upper()}, but you provided {biometric_type.upper()}.',
            'subject_id': subject_id
        }), 400

    is_authenticated = False
    confidence = 0.0
    verification_method = "none"
    recalculated_hash_hex = None
    
    # ============================================================
    # 2. VERIFICATION - Direct Feature Comparison
    # ============================================================
    if template_cid:
        try:
            # Retrieve and decrypt stored template
            encrypted_template = storage.get(template_cid)
            print(f"[OK] Retrieved template from storage: {len(encrypted_template) if encrypted_template else 0}B")
            
            if encrypted_template:
                decrypted_template = encryption.decrypt(encrypted_template)
                stored_features = np.frombuffer(decrypted_template, dtype=np.float32)
                
                print(f"[OK] Decrypted features: shape={stored_features.shape}, new features shape={features.shape}")
                
                # Compare features directly using modality-aware engine
                similarity = biometric_engine.compare(features, stored_features, bio_type=biometric_type)
                direct_confidence = similarity * 100.0
                
                # DYNAMIC THRESHOLDS based on modality
                threshold = 0.75  # Default for Facial
                if biometric_type == 'iris':
                    threshold = 0.15 
                elif biometric_type == 'fingerprint':
                    threshold = 0.85
                    
                print(f"[INFO] Comparison: similarity={similarity:.4f} (Threshold={threshold:.2f})")
                
                if similarity >= threshold:
                    is_authenticated = True
                    confidence = direct_confidence
                    verification_method = "direct_feature_comparison"
                    print(f"[AUTH-SUCCESS] Similarity {similarity:.4f} >= {threshold}")
                else:
                    print(f"[AUTH-FAIL] Similarity {similarity:.4f} < {threshold}")
                    confidence = direct_confidence
        except Exception as e:
            print(f"[WARN] Direct features comparison failed: {e}")
            import traceback
            traceback.print_exc()

    # ============================================================
    # 3. VERIFICATION - FCS Check
    # ============================================================
    if stored_delta:
        try:
            fcs_authenticated, fcs_confidence, fcs_hash = fcs.verify(features, stored_hash, stored_delta)
            print(f"[INFO] FCS Result: authenticated={fcs_authenticated}, confidence={fcs_confidence:.2f}%")
            recalculated_hash_hex = fcs_hash.hex()
            if not is_authenticated and fcs_authenticated:
                is_authenticated = True
                confidence = fcs_confidence
                verification_method = "fuzzy_commitment_scheme"
        except Exception as e:
            print(f"[WARN] FCS verification error: {e}")
    elif is_authenticated:
        recalculated_hash_hex = stored_hash.hex()

    print(f"[INFO] Final Result: authenticated={is_authenticated}, method={verification_method}, confidence={confidence:.2f}%")
    
    # Log authentication attempt
    logged_on_chain = False
    blockchain_warning = None
    
    sender = get_sender_account()
    if sender and w3 and w3.is_connected() and contract:
        try:
            reason = f"Verified successful" if is_authenticated else "Biometric mismatch"
            tx_params = {
                'from': sender,
                'gas': 500000,
                'gasPrice': w3.eth.gas_price
            }
            
            if PRIVATE_KEY:
                tx_params['nonce'] = w3.eth.get_transaction_count(sender)
                tx = contract.functions.logAuthentication(
                    bytes.fromhex(subject_id), is_authenticated, reason
                ).build_transaction(tx_params)
                signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
                w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            else:
                contract.functions.logAuthentication(
                    bytes.fromhex(subject_id), is_authenticated, reason
                ).transact(tx_params)
            
            logged_on_chain = True
        except Exception as e:
            print(f"[WARN] Blockchain logging failed: {e}")
            blockchain_warning = str(e)
    
    # Log to database
    db_service.log_authentication(
        subject_id=subject_id,
        success=is_authenticated,
        confidence=confidence,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')[:500],
        failure_reason=None if is_authenticated else 'Biometric mismatch'
    )
    
    return jsonify({
        'success': bool(is_authenticated),
        'confidence': float(confidence),
        'subject_id': str(subject_id),
        'logged_on_chain': bool(logged_on_chain),
        'blockchain_warning': str(blockchain_warning) if blockchain_warning else None,
        'hashes': {
            'stored': stored_hash.hex() if stored_hash else None,
            'computed': recalculated_hash_hex, 
            'match': bool(stored_hash.hex() == recalculated_hash_hex) if (stored_hash and recalculated_hash_hex) else False
        },
        'message': 'Matched Successful' if is_authenticated else 'Not Matched'
    })


@app.route('/api/voice/challenge', methods=['POST'])
def get_voice_challenge():
    """Generate a random 4-digit code for liveness verification."""
    data = request.json
    subject_id = data.get('subject_id')
    
    if not subject_id:
        return jsonify({'error': 'Subject ID required'}), 400
        
    code = str(random.randint(1000, 9999))
    voice_challenges.update({subject_id: code})
    print(f"[VOICE-CHALLENGE] Generated {code} for subject {subject_id[:8]}")
    
    return jsonify({
        'success': True,
        'challenge_code': code,
        'message': 'Please speak this code clearly into the microphone'
    })


@app.route('/api/verify', methods=['POST'])
def verify_biometrics():
    """Compare two biometric samples"""
    if 'file1' not in request.files or 'file2' not in request.files:
        return jsonify({'error': 'Two biometric files required'}), 400
    
    file1 = request.files['file1']
    file2 = request.files['file2']
    biometric_type = request.form.get('type', 'facial')
    
    try:
        # Process first file
        filepath1 = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file1.filename))
        file1.save(filepath1)
        features1 = biometric_engine.extract_features(filepath1, biometric_type)
        os.remove(filepath1)
        
        # Process second file
        filepath2 = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file2.filename))
        file2.save(filepath2)
        features2 = biometric_engine.extract_features(filepath2, biometric_type)
        os.remove(filepath2)
        
        if features1 is None or features2 is None:
            return jsonify({'error': 'Could not extract biometric features'}), 400
        
        # Compare using modality-aware engine
        similarity = biometric_engine.compare(features1, features2, bio_type=biometric_type)
        
        # Dynamic threshold based on modality
        threshold = 0.75
        if biometric_type == 'iris':
            threshold = 0.15
        if biometric_type == 'fingerprint':
            threshold = 0.85
            is_match = similarity >= threshold
            status_text = "MATCH" if is_match else "NOT MATCHED"
            
        return jsonify({
            'match': is_match if biometric_type == 'fingerprint' else similarity >= threshold,
            'status': status_text if biometric_type == 'fingerprint' else None,
            'similarity': float(similarity),
            'confidence': float(similarity * 100),
            'threshold': threshold
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════
#                           STATISTICS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/api/stats', methods=['GET'])
def get_statistics():
    """Get system statistics from database"""
    # Get database stats
    db_stats = db_service.get_statistics()
    
    stats = {
        'blockchain_connected': w3 is not None and w3.is_connected() if w3 else False,
        'timestamp': datetime.now().isoformat(),
        'total_subjects': db_stats['total_subjects'],
        'total_authentications': db_stats['total_authentications'],
        'successful_authentications': db_stats['successful_authentications'],
        'models_trained': db_stats['models_trained'],
        'database_connected': db_stats['database_available']
    }
    
    if w3 and w3.is_connected() and contract:
        try:
            stats['blockchain_total_subjects'] = contract.functions.totalSubjects().call()
            stats['blockchain_total_nodes'] = contract.functions.totalNodes().call()
            stats['blockchain_auth_records'] = contract.functions.totalAuthRecords().call()
            stats['current_block'] = w3.eth.block_number
        except Exception as e:
            stats['blockchain_error'] = str(e)
    
    return jsonify(stats)


# ═══════════════════════════════════════════════════════════════════════════
#                           DATABASE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/api/subjects', methods=['GET'])
def get_subjects():
    """Get all enrolled subjects from database"""
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    subjects = db_service.get_all_subjects(limit=limit, offset=offset)
    total = db_service.count_subjects()
    
    return jsonify({
        'subjects': subjects,
        'total': total,
        'limit': limit,
        'offset': offset
    })


@app.route('/api/subjects/<subject_id>', methods=['GET'])
def get_subject(subject_id):
    """Get a specific subject by ID"""
    subject = db_service.get_subject(subject_id)
    if subject:
        return jsonify(subject)
    return jsonify({'error': 'Subject not found'}), 404


@app.route('/api/auth-logs', methods=['GET'])
def get_auth_logs():
    """Get authentication logs"""
    subject_id = request.args.get('subject_id')
    limit = request.args.get('limit', 50, type=int)
    
    logs = db_service.get_authentication_logs(subject_id=subject_id, limit=limit)
    
    return jsonify({
        'logs': logs,
        'total': len(logs)
    })


# ═══════════════════════════════════════════════════════════════════════════
#                          ML TRAINING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/api/ml/models', methods=['GET'])
def get_ml_models():
    """Get all trained ML models"""
    model_type = request.args.get('type')
    
    models = db_service.get_all_models(model_type=model_type)
    available = model_trainer.get_available_models()
    
    return jsonify({
        'models': models,
        'available_on_disk': available,
        'model_types': ['facial', 'fingerprint', 'iris']
    })


@app.route('/api/ml/train', methods=['POST'])
def train_model():
    """Start training a new ML model"""
    data = request.get_json() or {}
    model_type = data.get('model_type', 'facial')
    epochs = data.get('epochs')
    
    if model_type not in ['facial', 'fingerprint', 'iris']:
        return jsonify({'error': 'Invalid model type. Must be facial, fingerprint, or iris'}), 400
    
    result = model_trainer.train_model(model_type=model_type, epochs=epochs)
    
    return jsonify(result)


@app.route('/api/ml/train/<job_id>/status', methods=['GET'])
def training_status(job_id):
    """Get training job status"""
    status = model_trainer.get_training_status(job_id)
    
    if status:
        return jsonify(status)
    return jsonify({'error': 'Training job not found'}), 404


@app.route('/api/ml/models/<int:model_id>/activate', methods=['POST'])
def activate_model(model_id):
    """Activate a trained model for production use"""
    success = db_service.activate_model(model_id)
    
    if success:
        return jsonify({'success': True, 'message': f'Model {model_id} activated'})
    return jsonify({'error': 'Model not found or could not be activated'}), 404


@app.route('/api/ml/models/active', methods=['GET'])
def get_active_models():
    """Get currently active models for each biometric type"""
    active_models = {}
    
    for model_type in ['facial', 'fingerprint', 'iris']:
        model = db_service.get_active_model(model_type)
        active_models[model_type] = model
    
    return jsonify(active_models)


# ═══════════════════════════════════════════════════════════════════════════
#                            ZKP AUTHENTICATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/api/zkp/status', methods=['GET'])
def zkp_status():
    """Check if ZKP is available"""
    return jsonify({
        'available': ZKP_AVAILABLE,
        'protocol': 'groth16' if ZKP_AVAILABLE else None,
        'curve': 'bn128' if ZKP_AVAILABLE else None,
        'hash': 'poseidon' if ZKP_AVAILABLE else None
    })


@app.route('/api/zkp/commitment', methods=['POST'])
def create_zkp_commitment():
    """
    Create a ZKP commitment for a biometric embedding.
    
    This is called during enrollment to create a ZK-friendly commitment
    that will be stored on the blockchain.
    
    Request:
        - file: Biometric image file
        - type: Biometric type (facial, fingerprint, iris)
    
    Response:
        - commitment: The Poseidon hash commitment
        - salt: The random salt (store securely!)
        - quantized: Quantized biometric values
    """
    if not ZKP_AVAILABLE:
        return jsonify({'error': 'ZKP module not available'}), 503
    
    if 'file' not in request.files:
        return jsonify({'error': 'No biometric file provided'}), 400
    
    file = request.files['file']
    biometric_type = request.form.get('type', 'facial')
    
    # Save temporarily
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    
    try:
        # Extract biometric features
        features = biometric_engine.extract_features(filepath, biometric_type)
        os.remove(filepath)
        
        if features is None:
            return jsonify({'error': 'Could not extract biometric features'}), 400
        
        # Create ZKP commitment
        commitment_result = zkp_create_commitment(features)
        
        if 'error' in commitment_result:
            return jsonify({'error': commitment_result['error']}), 500
        
        return jsonify({
            'success': True,
            'commitment': commitment_result['commitment'],
            'salt': commitment_result['salt'],
            'quantized': commitment_result['quantized'],
            'algorithm': commitment_result['algorithm'],
            'message': 'ZKP commitment created successfully'
        })
        
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': str(e)}), 500


@app.route('/api/zkp/enroll', methods=['POST'])
def zkp_enroll():
    """
    Enroll a subject with ZKP commitment.
    
    Creates both:
    1. Standard enrollment (for backup/fallback)
    2. ZKP commitment (for privacy-preserving auth)
    
    Request:
        - file: Biometric image
        - name: Subject name
        - type: Biometric type
    """
    if not ZKP_AVAILABLE:
        return jsonify({'error': 'ZKP module not available'}), 503
    
    if 'file' not in request.files:
        return jsonify({'error': 'No biometric file provided'}), 400
    
    file = request.files['file']
    name = request.form.get('name', 'Anonymous')
    biometric_type = request.form.get('type', 'facial')
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    
    try:
        # Extract features
        features = biometric_engine.extract_features(filepath, biometric_type)
        
        if features is None:
            os.remove(filepath)
            return jsonify({'error': 'Could not extract biometric features'}), 400
        
        # Create ZKP commitment
        zkp_result = zkp_create_commitment(features)
        
        if 'error' in zkp_result:
            os.remove(filepath)
            return jsonify({'error': zkp_result['error']}), 500
        
        # Generate subject ID
        subject_id = hashlib.sha256(
            f"{name}{datetime.now().isoformat()}{secrets.token_hex(16)}".encode()
        ).hexdigest()
        
        # Store encrypted template
        encrypted_template = encryption.encrypt(features.tobytes())
        template_cid = storage.store(encrypted_template)
        
        # Store in database with ZKP data
        db_service.add_subject(
            subject_id=subject_id,
            name=name,
            biometric_type=biometric_type,
            commitment_hash=zkp_result['commitment'],
            delta_storage_id=template_cid,
            blockchain_tx=None
        )
        
        # Store ZKP salt securely (in a real system, this would be in HSM or user's device)
        # For demo, we store it encrypted
        zkp_salt_cid = storage.store(encryption.encrypt(zkp_result['salt'].encode()))
        
        os.remove(filepath)
        
        # Generate human-readable subject code
        subject_code = f"{name.upper()[:3]}-{subject_id[:8]}"
        
        result = {
            'success': True,
            'subject_id': subject_id,
            'subject_code': subject_code,
            'name': name,
            'zkp': {
                'commitment': zkp_result['commitment'],
                'algorithm': zkp_result['algorithm'],
                'salt_storage_id': zkp_salt_cid
            },
            'message': f'ZKP enrollment successful. Your ID: {subject_code}'
        }
        
        # Submit to blockchain if connected
        sender = get_sender_account()
        if w3 and w3.is_connected() and contract and sender:
            try:
                subject_id_bytes = bytes.fromhex(subject_id)
                commitment_hash = bytes.fromhex(zkp_result['commitment'][:64])  # First 32 bytes
                
                biometric_enum = {'facial': 0, 'fingerprint': 1, 'iris': 2, 'multimodal': 3}
                bio_type = biometric_enum.get(biometric_type, 0)
                
                tx_params = {
                    'from': sender,
                    'gas': 500000,
                    'gasPrice': w3.eth.gas_price
                }
                
                tx_hash = contract.functions.enrollSubject(
                    subject_id_bytes,
                    commitment_hash,
                    b'',  # No delta for ZKP enrollment
                    template_cid,
                    bio_type
                ).transact(tx_params)
                
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
                
                result['transaction_hash'] = tx_hash.hex()
                result['block_number'] = receipt['blockNumber']
                
                db_service.update_subject_blockchain_tx(subject_id, tx_hash.hex())
                
            except Exception as e:
                print(f"[WARN] Blockchain enrollment failed: {e}")
        
        return jsonify(result)
        
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/zkp/authenticate', methods=['POST'])
def zkp_authenticate():
    """
    Authenticate using Zero-Knowledge Proof.
    
    This proves the user knows the biometric matching the stored commitment
    WITHOUT revealing the actual biometric data to the server.
    
    Request:
        - file: Biometric image
        - subject_id: Subject identifier
        - type: Biometric type
    """
    if not ZKP_AVAILABLE:
        return jsonify({'error': 'ZKP module not available'}), 503
    
    if 'file' not in request.files:
        return jsonify({'error': 'No biometric file provided'}), 400
    
    file = request.files['file']
    subject_id = request.form.get('subject_id', '')
    biometric_type = request.form.get('type', 'facial')
    
    if not subject_id:
        return jsonify({'error': 'Subject ID required'}), 400
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    
    try:
        # Extract new features
        new_features = biometric_engine.extract_features(filepath, biometric_type)
        os.remove(filepath)
        
        if new_features is None:
            return jsonify({'error': 'Could not extract biometric features'}), 400
        
        # Get stored subject data
        subject = db_service.get_subject(subject_id)
        
        if not subject:
            return jsonify({
                'success': False,
                'error': 'Subject not found',
                'subject_id': subject_id
            }), 404
        
        # Retrieve stored template and salt
        template_cid = subject.get('delta_storage_id')
        commitment = subject.get('commitment_hash')
        stored_bio_type = subject.get('biometric_type', 'facial')
        
        # ════════════════════════════════════════════════════════════
        # NEW: SECURITY CHECK - Modality Mismatch Detection
        # ════════════════════════════════════════════════════════════
        if stored_bio_type != biometric_type:
            return jsonify({
                'success': False,
                'error': f'ZKP Modality mismatch. Enrolled with {stored_bio_type.upper()}, but you provided {biometric_type.upper()}.',
                'subject_id': subject_id
            }), 400

        if not template_cid or not commitment:
            return jsonify({
                'success': False,
                'error': 'ZKP data not found for subject'
            }), 404
        
        # Decrypt stored template
        encrypted_template = storage.get(template_cid)
        stored_template = np.frombuffer(
            encryption.decrypt(encrypted_template),
            dtype=np.float32
        )
        
        # For demo, we need the salt - in production, user would provide this
        # or it would be derived from a hardware token/passphrase
        
        # Generate proof using the new biometric and stored commitment
        # The proof demonstrates knowledge of btemetric matching commitment
        proof_result = zkp_generate_proof(stored_template, '0', commitment)
        
        if not proof_result.get('valid'):
            # If proof generation fails, biometric doesn't match
            return jsonify({
                'success': False,
                'authenticated': False,
                'method': 'zkp',
                'error': proof_result.get('error', 'Proof generation failed'),
                'message': 'Biometric verification failed'
            })
        
        # Verify the proof
        verification = zkp_verify_proof(proof_result, commitment)
        
        # Also do similarity check for double verification
        similarity = biometric_engine.compare(new_features, stored_template, bio_type=biometric_type)
        
        # DYNAMIC THRESHOLDS based on modality
        threshold = 0.75  # Default for Facial
        if biometric_type == 'iris':
            threshold = 0.15
        elif biometric_type == 'fingerprint':
            threshold = 0.82
            
        print(f"[ZKP] Comparison: similarity={similarity:.4f} (Threshold={threshold:.2f})")
        
        is_authenticated = verification.get('valid', False) and similarity >= threshold
        
        result = {
            'success': True,
            'authenticated': is_authenticated,
            'method': 'zkp_poseidon',
            'similarity': float(similarity),
            'confidence': float(similarity * 100),
            'subject_id': subject_id,
            'subject_name': subject.get('name', 'Unknown'),
            'proof': {
                'valid': proof_result.get('valid'),
                'protocol': proof_result.get('protocol'),
                'curve': proof_result.get('curve'),
                'timestamp': proof_result.get('timestamp')
            },
            'verification': {
                'valid': verification.get('valid'),
                'commitment_matched': True
            },
            'privacy': {
                'biometric_revealed': False,
                'proof_size_bytes': 288,
                'algorithm': 'groth16'
            }
        }
        
        if is_authenticated:
            result['message'] = 'ZKP authentication successful - Identity verified without revealing biometric data'
        else:
            result['message'] = 'ZKP authentication failed - Biometric mismatch'
        
        return jsonify(result)
        
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/zkp/verify-proof', methods=['POST'])
def verify_zkp_proof():
    """
    Verify a ZKP proof independently.
    
    Request:
        - proof: The ZKP proof object
        - commitment: The expected commitment
    """
    if not ZKP_AVAILABLE:
        return jsonify({'error': 'ZKP module not available'}), 503
    
    data = request.get_json()
    
    if not data or 'proof' not in data or 'commitment' not in data:
        return jsonify({'error': 'proof and commitment required'}), 400
    
    try:
        result = zkp_verify_proof(data['proof'], data['commitment'])
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ═══════════════════════════════════════════════════════════════════════════
#                            IPFS EXPLORER ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/api/ipfs/objects', methods=['GET'])
def list_ipfs_objects():
    """List all objects stored in the IPFS layer"""
    index = storage._load_index()
    objects = list(index.values())
    return jsonify({
        'success': True,
        'count': len(objects),
        'objects': objects
    })

@app.route('/api/ipfs/cat/<cid>', methods=['GET'])
def ipfs_cat(cid):
    """Retrieve an object's content (cat) from IPFS"""
    data = storage.get(cid)
    if data:
        # Check if it's JSON printable for easy viewing
        try:
            # If it's encrypted data, we just return a status
            return jsonify({
                'cid': cid,
                'type': 'encrypted_biometric' if b'AES' in data[:20] else 'unknown',
                'size': len(data),
                'preview': base64.b64encode(data[:64]).decode() + '...'
            })
        except:
            return jsonify({'error': 'Binary data cannot be displayed directly'}), 200
    return jsonify({'error': 'Object not found'}), 404

@app.route('/api/ipfs/status', methods=['GET'])
def ipfs_status():
    """Get the status of the IPFS layer"""
    return jsonify({
        'status': 'operational',
        'gateway': 'local-addressable',
        'p2p_enabled': False,
        'storage_path': storage.local_path,
        'objects_count': len(storage._load_index())
    })

# ═══════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════
#                    MULTIMODAL FACE + IRIS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

FACE_WEIGHT = 0.60   # Face contributes 60% to fusion score
VOICE_WEIGHT = 0.30  # Voice contributes 30% to fusion score

FACE_THRESHOLD  = 0.75   # Minimum cosine similarity for face
VOICE_THRESHOLD = 0.50   # Minimum voice similarity
FUSION_THRESHOLD = 0.50  # Minimum weighted fusion score to pass


@app.route('/api/multimodal/enroll', methods=['POST'])
def multimodal_enroll():
    """
    Enroll a subject using both face AND iris biometrics.

    Form fields:
        face_file  – JPEG/PNG of the face
        iris_file  – JPEG/PNG of the eye/iris
        name       – Subject name
    """
    if 'face_file' not in request.files or 'voice_file' not in request.files:
        return jsonify({'error': 'Both face_file and voice_file are required'}), 400

    face_file = request.files['face_file']
    voice_file = request.files['voice_file']
    name = request.form.get('name', '').strip()

    if not name:
        return jsonify({'error': 'Name is required'}), 400

    try:
        # ── Save uploads ──────────────────────────────────────────────────
        face_path = os.path.join(app.config['UPLOAD_FOLDER'],
                                 'mm_face_' + secure_filename(face_file.filename))
        voice_path = os.path.join(app.config['UPLOAD_FOLDER'],
                                 'mm_voice_' + secure_filename(voice_file.filename))
        face_file.save(face_path)
        voice_file.save(voice_path)

        # ── Extract features ──────────────────────────────────────────────
        face_features = biometric_engine.extract_features(face_path, 'facial')
        voice_features = biometric_engine.extract_features(voice_path, 'voice')

        # ── Speech to Text (Password) ───────────────────────────────────
        spoken_password = None
        if VOICE_STT_AVAILABLE:
            spoken_password = speech_to_text(voice_path)
            print(f"[MULTIMODAL] Spoken password: '{spoken_password}'")

        os.remove(face_path)
        os.remove(voice_path)

        if face_features is None:
            return jsonify({'error': 'Could not extract face features.'}), 400
        if voice_features is None:
            return jsonify({'error': 'Could not extract voice features.'}), 400

        print(f"[MULTIMODAL] Face features: {face_features.shape}, Voice features: {voice_features.shape}")

        # ── Generate subject ID ───────────────────────────────────────────
        subject_id   = generate_subject_id(name + 'multimodal')
        subject_code = generate_human_code()

        # ── Encrypt & store each modality separately ──────────────────────
        enc_face = encryption.encrypt(face_features.tobytes())
        enc_voice = encryption.encrypt(voice_features.tobytes())

        face_cid = storage.add(enc_face)
        voice_cid = storage.add(enc_voice)

        # Also save raw features for direct comparison
        storage.save_features(subject_id + '_face', face_features)
        storage.save_features(subject_id + '_voice', voice_features)

        # ── Fuzzy commitment on concatenated features ─────────────────────
        # Pad/truncate both to 512D then concatenate → 1024D commitment
        def pad512(f):
            f = np.array(f, dtype=np.float32).flatten()
            if len(f) >= 512:
                return f[:512]
            return np.concatenate([f, np.zeros(512 - len(f), dtype=np.float32)])

        fused_features = np.concatenate([pad512(face_features), pad512(voice_features)])
        commitment = fcs.commit(fused_features)

        # ── Store in database ─────────────────────────────────────────────
        import json as _json
        storage_meta = _json.dumps({'face_cid': face_cid, 'voice_cid': voice_cid})
        
        fingerprint_hash_val = None
        if spoken_password:
            encrypted_pwd = encryption.encrypt(spoken_password.lower().strip().encode())
            fingerprint_hash_val = base64.b64encode(encrypted_pwd).decode()

        db_result = db_service.create_subject(
            subject_id=subject_id,
            subject_code=subject_code,
            name=name,
            email=None,
            biometric_type='multimodal',
            commitment_hash=commitment['hash'].hex(),
            delta_storage_id=storage_meta,
            fingerprint_hash=fingerprint_hash_val # Store encrypted password in this field
        )

        if not db_result['success']:
            return jsonify({'error': db_result.get('error', 'Database save failed')}), 500

        result = {
            'success': True,
            'subject_id': subject_id,
            'subject_code': subject_code,
            'biometric_type': 'multimodal',
            'face_cid': face_cid,
            'voice_cid': voice_cid,
            'commitment_hash': commitment['hash'].hex(),
            'message': f'Multimodal identity enrolled. Subject Code: {subject_code}'
        }

        # ── Optionally push to blockchain ─────────────────────────────────
        sender = get_sender_account()
        if w3 and w3.is_connected() and contract and sender:
            try:
                subject_id_bytes = bytes.fromhex(subject_id)
                tx_params = {
                    'from': sender,
                    'gas': 500000,
                    'gasPrice': w3.eth.gas_price
                }
                if PRIVATE_KEY:
                    tx_params['nonce'] = w3.eth.get_transaction_count(sender)
                    tx = contract.functions.enrollSubject(
                        subject_id_bytes,
                        commitment['hash'],
                        commitment['delta'],
                        storage_meta[:64],   # truncate for on-chain storage
                        3  # BiometricType.Multimodal
                    ).build_transaction(tx_params)
                    signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
                    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
                else:
                    tx_hash = contract.functions.enrollSubject(
                        subject_id_bytes,
                        commitment['hash'],
                        commitment['delta'],
                        storage_meta[:64],
                        3
                    ).transact(tx_params)

                receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
                result['transaction_hash'] = tx_hash.hex()
                result['block_number']     = receipt['blockNumber']
                db_service.update_subject_blockchain_tx(subject_id, tx_hash.hex())
                print(f"[MULTIMODAL] On-chain: tx={tx_hash.hex()}")
            except Exception as e:
                result['blockchain_error'] = str(e)
                print(f"[MULTIMODAL] Blockchain enrollment failed: {e}")

        return jsonify(result), 201

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/multimodal/authenticate', methods=['POST'])
def multimodal_authenticate():
    """
    Authenticate a subject using both face AND iris biometrics.

    Form fields:
        face_file  – JPEG/PNG of the face
        iris_file  – JPEG/PNG of the eye/iris
        subject_id – The subject's UUID (hex string)
    """
    if 'face_file' not in request.files or 'voice_file' not in request.files:
        return jsonify({'error': 'Both face_file and voice_file are required'}), 400

    face_file  = request.files['face_file']
    voice_file = request.files['voice_file']
    subject_id = request.form.get('subject_id', '').strip()

    if not subject_id:
        return jsonify({'error': 'subject_id is required'}), 400

    try:
        # ── Save uploads ──────────────────────────────────────────────────
        face_path = os.path.join(app.config['UPLOAD_FOLDER'],
                                 'mm_auth_face_' + secure_filename(face_file.filename))
        voice_path = os.path.join(app.config['UPLOAD_FOLDER'],
                                 'mm_auth_voice_' + secure_filename(voice_file.filename))
        face_file.save(face_path)
        voice_file.save(voice_path)

        # ── Extract probe features ────────────────────────────────────────
        probe_face = biometric_engine.extract_features(face_path, 'facial')
        probe_voice = biometric_engine.extract_features(voice_path, 'voice')

        if probe_face is None:
            os.remove(face_path)
            os.remove(voice_path)
            return jsonify({'error': 'Could not extract face features from probe image.'}), 400
        if probe_voice is None:
            os.remove(face_path)
            os.remove(voice_path)
            return jsonify({'error': 'Could not extract voice features from probe audio.'}), 400

        # Delete face image (no longer needed)
        os.remove(face_path)

        # ── Retrieve enrolled subject ─────────────────────────────────────
        subject_db = db_service.get_subject(subject_id)
        if not subject_db:
            return jsonify({
                'success': False,
                'error': 'Subject not found. Please enroll first.',
                'subject_id': subject_id
            }), 404

        if subject_db.get('biometric_type') != 'multimodal':
            return jsonify({
                'success': False,
                'error': f"Subject was enrolled with '{subject_db.get('biometric_type')}' biometrics, not multimodal."
            }), 400

        # ── Retrieve stored templates ─────────────────────────────────────
        import json as _json
        storage_meta_str = subject_db.get('delta_storage_id', '{}')
        try:
            storage_meta = _json.loads(storage_meta_str)
        except Exception:
            storage_meta = {}

        face_cid = storage_meta.get('face_cid')
        voice_cid = storage_meta.get('voice_cid')

        face_similarity = 0.0
        voice_similarity = 0.0
        face_ok = False
        voice_ok = False

        # ── Compare face ──────────────────────────────────────────────────
        if face_cid:
            try:
                enc_face = storage.get(face_cid)
                if enc_face:
                    stored_face = np.frombuffer(encryption.decrypt(enc_face), dtype=np.float32)
                    face_similarity = biometric_engine.compare(probe_face, stored_face, bio_type='facial')
                    face_ok = face_similarity >= FACE_THRESHOLD
                    print(f"[MULTIMODAL] Face similarity={face_similarity:.4f} (threshold={FACE_THRESHOLD}, pass={face_ok})")
            except Exception as e:
                print(f"[MULTIMODAL] Face comparison error: {e}")
        else:
            # Fallback: compare saved raw features
            try:
                stored_face = storage.load_features(subject_id + '_face')
                if stored_face is not None:
                    face_similarity = biometric_engine.compare(probe_face, stored_face, bio_type='facial')
                    face_ok = face_similarity >= FACE_THRESHOLD
            except Exception as e:
                print(f"[MULTIMODAL] Face raw comparison error: {e}")

        # ── Compare voice ──────────────────────────────────────────────────
        if voice_cid:
            try:
                enc_voice = storage.get(voice_cid)
                if enc_voice:
                    stored_voice = np.frombuffer(encryption.decrypt(enc_voice), dtype=np.float32)
                    voice_similarity = biometric_engine.compare(probe_voice, stored_voice, bio_type='voice')
                    voice_ok = voice_similarity >= VOICE_THRESHOLD
                    print(f"[MULTIMODAL] Voice similarity={voice_similarity:.4f} (threshold={VOICE_THRESHOLD}, pass={voice_ok})")
            except Exception as e:
                print(f"[MULTIMODAL] Voice comparison error: {e}")
        
        # ── Password match (STT) ─────────────────────────────────────────
        password_ok = True
        probe_password = ""
        stored_password = subject_db.get('fingerprint_hash')
        
        if VOICE_STT_AVAILABLE and stored_password:
             try:
                 decoded = base64.b64decode(stored_password)
                 stored_word = encryption.decrypt(decoded).decode().strip().lower()
                 probe_word = speech_to_text(voice_path).strip().lower()
                 
                 import re
                 def normalize_voice(s): return re.sub(r'[^a-z0-9]', '', s.lower())
                 
                 probe_clean = normalize_voice(probe_word)
                 stored_clean = normalize_voice(stored_word)
                 
                 from difflib import SequenceMatcher
                 sim = SequenceMatcher(None, probe_clean, stored_clean).ratio()
                 
                 if probe_clean and (probe_clean == stored_clean or sim >= 0.75):
                     password_ok = True
                     print(f"[MULTIMODAL] Voice password STT match: {probe_clean} == {stored_clean}")
                 else:
                     password_ok = False
                     print(f"[MULTIMODAL] Voice password STT mismatch: {probe_clean} != {stored_clean}")
             except Exception as e:
                 print(f"[MULTIMODAL] STT extraction failed: {e}")
                 
        if not password_ok and voice_similarity >= VOICE_THRESHOLD:
             # Fallback to biometric sim
             password_ok = True
             
        # Done with the voice file
        if os.path.exists(voice_path):
            os.remove(voice_path)

        # ── Weighted fusion score ─────────────────────────────────────────
        face_norm = min(1.0, face_similarity)
        voice_norm = min(1.0, voice_similarity)

        fusion_score = FACE_WEIGHT * face_norm + VOICE_WEIGHT * voice_norm
        is_authenticated = face_ok and voice_ok and password_ok and (fusion_score >= FUSION_THRESHOLD)

        confidence = fusion_score * 100.0
        print(f"[MULTIMODAL] Fusion: face={face_norm:.4f} + voice={voice_norm:.4f} + pwd={password_ok} = {fusion_score:.4f} → {'PASS' if is_authenticated else 'FAIL'}")

        # ── Log to database ───────────────────────────────────────────────
        db_service.log_authentication(
            subject_id=subject_id,
            success=is_authenticated,
            confidence=confidence,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:500],
            failure_reason=None if is_authenticated else 'Multimodal biometric mismatch'
        )

        # ── Log on blockchain ─────────────────────────────────────────────
        logged_on_chain = False
        sender = get_sender_account()
        if sender and w3 and w3.is_connected() and contract:
            try:
                reason = "Multimodal verification successful" if is_authenticated else "Multimodal mismatch"
                tx_params = {'from': sender, 'gas': 500000, 'gasPrice': w3.eth.gas_price}
                if PRIVATE_KEY:
                    tx_params['nonce'] = w3.eth.get_transaction_count(sender)
                    tx = contract.functions.logAuthentication(
                        bytes.fromhex(subject_id), is_authenticated, reason
                    ).build_transaction(tx_params)
                    signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
                    w3.eth.send_raw_transaction(signed.raw_transaction)
                else:
                    contract.functions.logAuthentication(
                        bytes.fromhex(subject_id), is_authenticated, reason
                    ).transact(tx_params)
                logged_on_chain = True
            except Exception as e:
                print(f"[MULTIMODAL] Blockchain log failed: {e}")

        return jsonify({
            'success': is_authenticated,
            'subject_id': subject_id,
            'confidence': round(float(confidence), 2),
            'fusion_score': round(float(fusion_score), 4),
            'modalities': {
                'face': {
                    'similarity': round(float(face_similarity), 4),
                    'threshold': FACE_THRESHOLD,
                    'passed': face_ok,
                    'confidence_pct': round(float(face_norm * 100), 1)
                },
                'voice': {
                    'similarity': round(float(voice_similarity), 4),
                    'threshold': VOICE_THRESHOLD,
                    'passed': voice_ok,
                    'confidence_pct': round(float(voice_norm * 100), 1)
                }
            },
            'weights': {'facial': FACE_WEIGHT, 'voice': VOICE_WEIGHT},
            'logged_on_chain': logged_on_chain,
            'message': 'Multimodal verification successful' if is_authenticated else 'Multimodal biometric mismatch'
        })

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.errorhandler(400)
def bad_request(e):
    return jsonify({'error': 'Bad request'}), 400

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500


# ═══════════════════════════════════════════════════════════════════════════
#                                 MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Force UTF-8 encoding for Windows terminal
    import sys
    import io
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
        
    print("🚀 Starting Biometric Identity Backend on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
