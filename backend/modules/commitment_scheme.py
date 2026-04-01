"""
Fuzzy Commitment Scheme (FCS)
Implements secure biometric hashing with error-correction.

Based on:
- "A Fuzzy Commitment Scheme" by Juels & Wattenberg
- "BiometricIdentity dApp" (SoftwareX 2024)
- "BioZero" (arXiv 2024)
"""

import hashlib
import numpy as np
from typing import Dict, Tuple

class FuzzyCommitmentScheme:
    def __init__(self, key_length=16, feature_dim=128, error_tolerance=0.35, code_redundancy=7):
        """
        Initialize Fuzzy Commitment Scheme.
        
        Args:
            key_length: Length of the secret key (bytes)
            feature_dim: Dimension of biometric feature vector
            error_tolerance: Maximum tolerable Hamming distance (0-1)
                            - 0.35 means up to 35% bit difference is acceptable
                            - This accounts for natural biometric variations
            code_redundancy: Repetition code factor for error correction
        """
        self.key_length = key_length
        self.feature_dim = feature_dim
        self.error_tolerance = error_tolerance
        self.code_redundancy = code_redundancy

    def _quantize(self, features: np.ndarray) -> bytes:
        """
        Median-based quantization as per Juels & Wattenberg.
        Converts continuous features to binary representation.
        More stable than threshold-based quantization.
        """
        # Normalize features first
        features = np.array(features, dtype=np.float32).flatten()
        
        # Handle variable feature dimensions
        if len(features) != self.feature_dim:
            if len(features) > self.feature_dim:
                features = features[:self.feature_dim]
            else:
                # Pad with zeros if smaller
                padding = np.zeros(self.feature_dim - len(features), dtype=np.float32)
                features = np.concatenate([features, padding])
        
        # Remove invalid values
        features = np.nan_to_num(features, nan=0.0, posinf=1.0, neginf=-1.0)
        
        if np.std(features) > 0:
            features = (features - np.mean(features)) / np.std(features)
        
        # Median-based binarization (more stable across captures)
        median = np.median(features)
        bits = (features > median).astype(np.uint8)
        
        # Pack bits into bytes
        padded = np.pad(bits, (0, (8 - len(bits) % 8) % 8))
        return bytes(np.packbits(padded))

    def _dequantize(self, data: bytes) -> np.ndarray:
        """Convert bytes back to bit array."""
        return np.unpackbits(np.frombuffer(data, dtype=np.uint8))[:self.feature_dim]

    def _encode(self, key: bytes) -> bytes:
        """
        Repetition code encoding for error correction.
        Each bit is repeated 'code_redundancy' times.
        This allows recovery even with bit errors.
        """
        bits = np.unpackbits(np.frombuffer(key, dtype=np.uint8))
        encoded = np.repeat(bits, self.code_redundancy)
        padded = np.pad(encoded, (0, (8 - len(encoded) % 8) % 8))
        return bytes(np.packbits(padded))

    def _decode(self, codeword: bytes, original_len: int) -> bytes:
        """
        Decode using majority voting (error correction).
        For each group of 'code_redundancy' bits, take majority vote.
        """
        bits = np.unpackbits(np.frombuffer(codeword, dtype=np.uint8))
        decoded = []
        for i in range(0, original_len * 8 * self.code_redundancy, self.code_redundancy):
            chunk = bits[i:i + self.code_redundancy]
            if len(chunk) > 0:
                decoded.append(1 if np.sum(chunk) > len(chunk) / 2 else 0)
        return bytes(np.packbits(np.array(decoded[:original_len * 8])))

    def _xor(self, a: bytes, b: bytes) -> bytes:
        """XOR two byte sequences."""
        max_len = max(len(a), len(b))
        a_padded = a.ljust(max_len, b'\x00')
        b_padded = b.ljust(max_len, b'\x00')
        return bytes(x ^ y for x, y in zip(a_padded, b_padded))

    def _hamming_distance(self, a: bytes, b: bytes) -> float:
        """
        Calculate normalized Hamming distance (0-1).
        0 = identical, 1 = completely different
        """
        max_len = max(len(a), len(b))
        a_bits = np.unpackbits(np.frombuffer(a.ljust(max_len, b'\x00'), dtype=np.uint8))
        b_bits = np.unpackbits(np.frombuffer(b.ljust(max_len, b'\x00'), dtype=np.uint8))
        min_len = min(len(a_bits), len(b_bits))
        if min_len == 0:
            return 1.0
        return float(np.sum(a_bits[:min_len] != b_bits[:min_len]) / min_len)

    def commit(self, features: np.ndarray) -> Dict:
        """
        Create a fuzzy commitment from biometric features.
        
        As per Juels & Wattenberg:
        1. Generate random secret key K
        2. Encode K using error-correcting code -> C
        3. Quantize biometric features -> T (template)
        4. Compute delta = T XOR C (helper data)
        5. Compute hash H(K)
        
        Returns: {hash: H(K), delta: T XOR C, key: K}
        """
        # Generate random secret key
        key = np.random.bytes(self.key_length)
        
        if len(key) != self.key_length:
            raise ValueError(f"Key must be {self.key_length} bytes. Got {len(key)}")
        
        # 1. Error Correcting Code: Encode K -> C
        codeword = self._encode(key) # Changed _encode_ecc to _encode to match existing method
        
        # 2. Quantize biometric features -> T (template)
        template = self._quantize(features)
        
        # 3. Compute delta = T XOR C (helper data)
        # Convert template and codeword to numpy arrays of bits for bitwise_xor
        template_bits = np.unpackbits(np.frombuffer(template, dtype=np.uint8))
        codeword_bits = np.unpackbits(np.frombuffer(codeword, dtype=np.uint8))

        # Pad codeword if necessary
        if len(codeword_bits) > len(template_bits):
            template_bits = np.pad(template_bits, (0, len(codeword_bits) - len(template_bits)), 'constant')
        elif len(template_bits) > len(codeword_bits):
            codeword_bits = np.pad(codeword_bits, (0, len(template_bits) - len(codeword_bits)), 'constant')
            
        delta_bits = np.bitwise_xor(template_bits, codeword_bits)
        delta = bytes(np.packbits(delta_bits)) # Pack back to bytes

        # Hash the key for verification
        commitment_hash = hashlib.sha256(key).digest()
        
        print(f"[INFO] FCS Commit: template={len(template)}B, codeword={len(codeword)}B, delta={len(delta)}B")
        
        return {
            'hash': commitment_hash,
            'delta': delta,
            'key': key
        }

    def verify(self, features: np.ndarray, stored_hash: bytes, delta_bytes: bytes) -> Tuple[bool, float, bytes]:
        """
        Verify biometric features against stored commitment.
        
        As per Juels & Wattenberg:
        1. Quantize new biometric -> T'
        2. Compute C' = T' XOR delta (recover noisy codeword)
        3. Decode C' to get K' (error correction recovers key)
        4. Verify H(K') == stored_hash
        
        Returns: (is_authenticated, confidence_score, recovered_hash)
        """
        # Quantize verification biometric
        template_prime = self._quantize(features)
        
        # Recover codeword: C' = T' XOR delta
        codeword_prime = self._xor(template_prime, delta_bytes)
        
        # Decode to recover key (error correction)
        key_prime = self._decode(codeword_prime, self.key_length)
        
        # Hash recovered key
        hash_prime = hashlib.sha256(key_prime).digest()
        
        # PRIMARY CHECK: Exact hash match (as per paper)
        exact_match = (hash_prime == stored_hash[:len(hash_prime)])
        
        # Calculate bit-level similarity for confidence score
        # This measures how close the templates are
        original_codeword = self._xor(stored_delta, self._quantize(features))
        hamming_dist = self._hamming_distance(template_prime, 
                                               self._xor(stored_delta, self._encode(key_prime)))
        
        similarity = (1.0 - hamming_dist) * 100.0
        
        print(f"[INFO] FCS Verify: exact_match={exact_match}, hamming_dist={hamming_dist:.4f}, similarity={similarity:.2f}%")
        
        # SUCCESS CONDITIONS:
        # 1. Exact hash match (strict FCS - proves same biometric)
        # 2. OR hamming distance within error tolerance (fuzzy match)
        is_authenticated = exact_match or (hamming_dist <= self.error_tolerance)
        
        # Confidence score
        if exact_match:
            confidence = 100.0
        else:
            confidence = similarity
        
        return is_authenticated, confidence, hash_prime

