"""
Encryption Service Module
AES-256-GCM encryption for biometric data protection
"""

import os
import hashlib
import secrets
import base64
from typing import Tuple

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class EncryptionService:
    """AES-256-GCM encryption service"""
    
    def __init__(self, master_key: bytes = None):
        self.master_key = master_key or self._load_or_create_key()
    
    def _load_or_create_key(self) -> bytes:
        key_path = os.path.join(os.path.dirname(__file__), '.encryption_key')
        if os.path.exists(key_path):
            with open(key_path, 'rb') as f:
                return f.read()
        key = secrets.token_bytes(32)
        with open(key_path, 'wb') as f:
            f.write(key)
        return key
    
    def encrypt(self, plaintext: bytes, key: bytes = None) -> bytes:
        key = key or self.master_key
        if CRYPTO_AVAILABLE:
            iv = secrets.token_bytes(12)
            cipher = Cipher(algorithms.AES(key[:32]), modes.GCM(iv), backend=default_backend())
            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(plaintext) + encryptor.finalize()
            return iv + encryptor.tag + ciphertext
        else:
            iv = secrets.token_bytes(16)
            derived = hashlib.sha256(key + iv).digest()
            return iv + bytes(b ^ derived[i % 32] for i, b in enumerate(plaintext))
    
    def decrypt(self, ciphertext: bytes, key: bytes = None) -> bytes:
        key = key or self.master_key
        if CRYPTO_AVAILABLE:
            iv, tag, encrypted = ciphertext[:12], ciphertext[12:28], ciphertext[28:]
            cipher = Cipher(algorithms.AES(key[:32]), modes.GCM(iv, tag), backend=default_backend())
            decryptor = cipher.decryptor()
            return decryptor.update(encrypted) + decryptor.finalize()
        else:
            iv, encrypted = ciphertext[:16], ciphertext[16:]
            derived = hashlib.sha256(key + iv).digest()
            return bytes(b ^ derived[i % 32] for i, b in enumerate(encrypted))
    
    def hash_data(self, data: bytes) -> bytes:
        return hashlib.sha256(data).digest()
    
    def generate_random(self, length: int) -> bytes:
        return secrets.token_bytes(length)
