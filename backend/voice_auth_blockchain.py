import numpy as np
import random
import speech_recognition as sr
from resemblyzer import VoiceEncoder, preprocess_wav
try:
    import sounddevice as sd
except ImportError:
    sd = None
from scipy.io.wavfile import write
import hashlib
import pickle
import os
from web3 import Web3

# ---------------- CONFIG ---------------- #
# Adjusting port to 8545 to match your existing Ganache instance
GANACHE_URL = "http://127.0.0.1:8545"
# Note: User should update this after deploying the contract in Remix
CONTRACT_ADDRESS = "0x0000000000000000000000000000000000000000" 
ACCOUNT = None  # will be assigned after connection

# ABI (same as contract)
ABI = [
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

USER_DB = "user_embeddings.pkl"

# ---------------- INIT ---------------- #
print("🔗 Connecting to Blockchain...")
web3 = Web3(Web3.HTTPProvider(GANACHE_URL))

if not web3.is_connected():
    print("❌ Blockchain connection failed. Make sure Ganache is running on 8545.")
    # Fallback to dummy account for local testing if network is down
    ACCOUNT = "0x0000000000000000000000000000000000000000"
else:
    print("✅ Connected to Ganache")
    ACCOUNT = web3.eth.accounts[0]

try:
    contract = web3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=ABI)
except Exception:
    print("⚠️ Contract not found at address. Authentication will use local database only.")
    contract = None

print("🎙️ Initializing Voice Encoder (Resemblyzer)...")
encoder = VoiceEncoder()

# ---------------- AUDIO ---------------- #
def record_audio(filename, duration=5, fs=16000):
    if sd is None:
        print("❌ sounddevice not installed. Please install: pip install sounddevice")
        return False
    print(f"🎤 Recording for {duration} seconds...")
    try:
        audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='float32')
        sd.wait()
        write(filename, fs, (audio * 32767).astype(np.int16)) # Convert to 16-bit PCM for better compatibility
        print("✅ Recorded")
        return True
    except Exception as e:
        print(f"❌ Recording failed: {e}")
        return False

# ---------------- EMBEDDING ---------------- #
def get_embedding(file):
    wav = preprocess_wav(file)
    return encoder.embed_utterance(wav)

# ---------------- HASH ---------------- #
def generate_hash(embedding):
    return hashlib.sha256(embedding.tobytes()).hexdigest()

# ---------------- LOCAL STORAGE ---------------- #
def save_db(data):
    with open(USER_DB, "wb") as f:
        pickle.dump(data, f)

def load_db():
    if not os.path.exists(USER_DB):
        return {}
    with open(USER_DB, "rb") as f:
        return pickle.load(f)

# ---------------- BLOCKCHAIN ---------------- #
def store_hash_on_chain(user_id, hash_value):
    if not contract: return
    try:
        tx = contract.functions.storeHash(user_id, hash_value).transact({
            'from': ACCOUNT
        })
        web3.eth.wait_for_transaction_receipt(tx)
        print("🔗 Hash stored on blockchain")
    except Exception as e:
        print(f"❌ Blockchain store failed: {e}")

def get_hash_from_chain(user_id):
    if not contract: return None
    try:
        return contract.functions.getHash(user_id).call()
    except Exception:
        return None

# ---------------- REGISTER ---------------- #
def register():
    user_id = input("Enter User ID: ")
    if not user_id: return

    file = f"{user_id}_reg.wav"
    if record_audio(file, 5):
        embedding = get_embedding(file)
        hash_value = generate_hash(embedding)

        db = load_db()
        db[user_id] = embedding
        save_db(db)

        store_hash_on_chain(user_id, hash_value)
        print("✅ Registration Complete")
    else:
        print("❌ Registration Failed")

# ---------------- VERIFY ---------------- #
def verify_identity(stored, live, threshold=0.82):
    # Dot product of normalized vectors is Cosine Similarity
    score = np.dot(stored, live)
    print(f"Biometric Similarity Score: {score:.4f}")
    return score > threshold

def verify_liveness(file, code):
    r = sr.Recognizer()
    try:
        with sr.AudioFile(file) as source:
            audio = r.record(source)
            text = r.recognize_google(audio)
            print("You said:", text)
            # Check if code is in transcribed text
            return str(code) in text.replace(" ", "")
    except Exception as e:
        print(f"⚠️ Liveness check error (STT): {e}")
        return False

# ---------------- AUTH ---------------- #
def authenticate():
    user_id = input("Enter User ID: ")
    db = load_db()

    if user_id not in db:
        print("❌ User not found in local database")
        return

    stored_embedding = db[user_id]

    # --- DATA INTEGRITY GATE (Blockchain) ---
    blockchain_hash = get_hash_from_chain(user_id)
    if blockchain_hash:
        current_hash = generate_hash(stored_embedding)
        if blockchain_hash != current_hash:
            print("🚨 SECURITY ALERT: Local data has been tampered with!")
            print(f"   Stored: {current_hash[:10]}...")
            print(f"   Chain:  {blockchain_hash[:10]}...")
            return
        print("✅ Blockchain Integrity Verified")
    else:
        print("⚠️ Blockchain record missing for this ID (Local-only mode)")

    # --- LIVENESS GATE ---
    code = random.randint(1000, 9999)
    print(f"\n📢 ACTION REQUIRED: Please say this 4-digit code: [ {code} ]")

    file = f"{user_id}_live.wav"
    if record_audio(file, 5):
        live_embedding = get_embedding(file)

        # Dual Gate Verification
        is_user = verify_identity(stored_embedding, live_embedding)
        is_live = verify_liveness(file, code)

        print("\n" + "="*20)
        print("   FINAL RESULT")
        print("="*20)
        
        if not is_live:
            print("❌ LIVENESS FAILED: Code not detected or incorrect.")
        
        if is_user and is_live:
            print("🔓 ACCESS GRANTED: User identity and liveness confirmed.")
        elif is_user:
            print("❌ ACCESS DENIED: Identity matched, but liveness challenge failed.")
        else:
            print("❌ ACCESS DENIED: Voiceprint does not match registered user.")
    else:
        print("❌ Authentication recording failed.")

# ---------------- MAIN ---------------- #
def main():
    print("\n" + "*"*40)
    print(" ANTIGRAVITY VOICE AUTH SYSTEM ")
    print("*"*40)
    while True:
        print("\n1. Register (Voiceprint + Blockchain)")
        print("2. Authenticate (Biometric + Liveness + Chain)")
        print("3. Exit")
        choice = input("Choose: ")

        if choice == "1":
            register()
        elif choice == "2":
            authenticate()
        elif choice == "3":
            print("Exiting...")
            break
        else:
            print("Invalid choice")

if __name__ == "__main__":
    main()
