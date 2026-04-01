"""
ZKP Python Bridge Module

This module provides a Python interface to the JavaScript ZKP service.
It uses subprocess to call Node.js for the actual ZKP operations.
"""

import subprocess
import json
import os
import numpy as np
from typing import Dict, Any, Optional, List

# Path to the ZKP directory
ZKP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'zkp')


def _run_node_script(script_content: str) -> Dict[str, Any]:
    """
    Run a Node.js script and return the JSON result.
    """
    try:
        # Create a temporary script that imports zkp_service and runs the operation
        full_script = f"""
const zkp = require('{ZKP_DIR.replace(os.sep, '/')}/zkp_service.js');

async function main() {{
    try {{
        {script_content}
    }} catch (error) {{
        console.log(JSON.stringify({{ error: error.message }}));
    }}
}}

main();
"""
        
        result = subprocess.run(
            ['node', '-e', full_script],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=os.path.dirname(ZKP_DIR)
        )
        
        if result.returncode != 0:
            return {'error': result.stderr or 'Node.js execution failed'}
        
        # Parse JSON output
        output = result.stdout.strip()
        if output:
            return json.loads(output)
        return {'error': 'No output from Node.js'}
        
    except subprocess.TimeoutExpired:
        return {'error': 'ZKP operation timed out'}
    except json.JSONDecodeError as e:
        return {'error': f'Invalid JSON response: {str(e)}'}
    except Exception as e:
        return {'error': str(e)}


def create_commitment(embedding: np.ndarray) -> Dict[str, Any]:
    """
    Create a ZKP commitment from a biometric embedding.
    
    Args:
        embedding: NumPy array of biometric features (typically 128-dim)
    
    Returns:
        Dictionary with commitment, salt, and quantized values
    """
    # Convert numpy array to list for JSON serialization
    embedding_list = embedding.tolist() if isinstance(embedding, np.ndarray) else list(embedding)
    
    script = f"""
const embedding = {json.dumps(embedding_list)};
const result = await zkp.createCommitment(embedding);
console.log(JSON.stringify(result));
"""
    
    return _run_node_script(script)


def generate_proof(embedding: np.ndarray, salt: str, commitment: str) -> Dict[str, Any]:
    """
    Generate a ZKP proof for biometric authentication.
    
    Args:
        embedding: NumPy array of biometric features
        salt: The salt used during enrollment
        commitment: The commitment stored on blockchain
    
    Returns:
        ZKP proof object or error
    """
    embedding_list = embedding.tolist() if isinstance(embedding, np.ndarray) else list(embedding)
    
    script = f"""
const embedding = {json.dumps(embedding_list)};
const salt = "{salt}";
const commitment = "{commitment}";
const proof = await zkp.generateProof(embedding, salt, commitment);
console.log(JSON.stringify(proof));
"""
    
    return _run_node_script(script)


def verify_proof(proof: Dict[str, Any], commitment: str) -> Dict[str, Any]:
    """
    Verify a ZKP proof.
    
    Args:
        proof: The ZKP proof object
        commitment: The expected commitment
    
    Returns:
        Verification result
    """
    script = f"""
const proof = {json.dumps(proof)};
const commitment = "{commitment}";
const result = await zkp.verifyProof(proof, commitment);
console.log(JSON.stringify(result));
"""
    
    return _run_node_script(script)


def authenticate_with_zkp(
    new_embedding: np.ndarray,
    stored_embedding: np.ndarray,
    stored_salt: str,
    stored_commitment: str,
    threshold: float = 0.75
) -> Dict[str, Any]:
    """
    Full ZKP authentication flow.
    
    Args:
        new_embedding: Fresh biometric capture
        stored_embedding: Enrolled biometric template
        stored_salt: Salt from enrollment
        stored_commitment: Commitment from blockchain
        threshold: Similarity threshold (default 0.75)
    
    Returns:
        Authentication result with proof
    """
    new_list = new_embedding.tolist() if isinstance(new_embedding, np.ndarray) else list(new_embedding)
    stored_list = stored_embedding.tolist() if isinstance(stored_embedding, np.ndarray) else list(stored_embedding)
    
    script = f"""
const newEmbedding = {json.dumps(new_list)};
const storedEmbedding = {json.dumps(stored_list)};
const storedSalt = "{stored_salt}";
const storedCommitment = "{stored_commitment}";
const threshold = {threshold};
const result = await zkp.authenticateWithZKP(newEmbedding, storedEmbedding, storedSalt, storedCommitment, threshold);
console.log(JSON.stringify(result));
"""
    
    return _run_node_script(script)


# Direct Poseidon implementation in Python (for when Node.js is not available)
def poseidon_commitment_python(embedding: np.ndarray, salt_bytes: bytes = None) -> Dict[str, Any]:
    """
    Fallback Python implementation using SHA-256 (not a true ZK-friendly hash,
    but provides similar commitment properties for demonstration).
    
    For production, use the Node.js implementation with actual Poseidon.
    """
    import hashlib
    import secrets
    
    # Generate salt if not provided
    if salt_bytes is None:
        salt_bytes = secrets.token_bytes(32)
    
    # Quantize embedding to 8 elements
    quantized = []
    chunk_size = len(embedding) // 8
    for i in range(8):
        start = i * chunk_size
        end = min((i + 1) * chunk_size, len(embedding))
        avg = np.mean(embedding[start:end])
        # Scale to positive integer
        scaled = int((avg + 1) * 1e15)
        quantized.append(abs(scaled))
    
    # Create commitment using SHA-256 (substitute for Poseidon)
    hasher = hashlib.sha256()
    for q in quantized:
        hasher.update(q.to_bytes(16, 'big'))
    hasher.update(salt_bytes)
    
    commitment = hasher.hexdigest()
    
    return {
        'commitment': commitment,
        'salt': salt_bytes.hex(),
        'quantized': [str(q) for q in quantized],
        'algorithm': 'sha256_fallback',
        'inputSize': 9
    }


def test_zkp_python():
    """Test the Python ZKP bridge."""
    print("Testing Python ZKP Bridge...")
    
    # Create test embedding
    embedding = np.random.randn(128).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)  # Normalize
    
    print("\n1. Creating commitment...")
    result = create_commitment(embedding)
    print(f"   Result: {result}")
    
    if 'error' not in result:
        print("\n2. Generating proof...")
        proof = generate_proof(embedding, result['salt'], result['commitment'])
        print(f"   Valid: {proof.get('valid', False)}")
        
        if proof.get('valid'):
            print("\n3. Verifying proof...")
            verification = verify_proof(proof, result['commitment'])
            print(f"   Verified: {verification.get('valid', False)}")
    
    print("\nPython ZKP Bridge Test Complete!")


if __name__ == '__main__':
    test_zkp_python()
