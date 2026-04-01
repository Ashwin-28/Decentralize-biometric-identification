import sys
import io
import json
import os
from web3 import Web3

# Force UTF-8 for everything
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Configuration
RPC_URL = "http://127.0.0.1:8545"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

if not w3.is_connected():
    print("Error: Could not connect to Ganache")
    exit(1)

deployer_account = w3.eth.accounts[0]
print(f"Deploying from: {deployer_account}")

def deploy_contract(json_path):
    print(f"Loading {json_path}...")
    if not os.path.exists(json_path):
        print(f"  [ERR] File not found: {json_path}")
        return None

    with open(json_path, 'r', encoding='utf-8') as f:
        artifact = json.load(f)
    
    abi = artifact['abi']
    bytecode = artifact['bytecode']
    
    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    try:
        # Simple deployment without args
        tx_hash = Contract.constructor().transact({
            'from': deployer_account,
            'gas': 6000000 
        })
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        print(f"  [OK] Deployed {artifact['contractName']} at {tx_receipt.contractAddress}")
        return tx_receipt.contractAddress
    except Exception as e:
        import traceback
        print(f"  [ERR] Error deploying {artifact['contractName']}:")
        print(f"  [ERR-DEBUG] Error details: {e}")
        traceback.print_exc()
        return None

# Deploy sequence
registry_addr = deploy_contract('build/contracts/BiometricRegistry.json')
fingerprint_addr = deploy_contract('build/contracts/FingerprintRegistry.json')
voice_addr = deploy_contract('build/contracts/VoiceAuth.json')

# Update .env
# ... using registry_addr ...
env_path = 'backend/.env'
if registry_addr:
    print(f"Success! Registry: {registry_addr}")
    # Updating file logic...
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        with open(env_path, 'w', encoding='utf-8') as f:
           for line in lines:
               if line.startswith('CONTRACT_ADDRESS='):
                   f.write(f"CONTRACT_ADDRESS={registry_addr}\n")
               elif line.startswith('GANACHE_ACCOUNT='):
                   f.write(f"GANACHE_ACCOUNT={deployer_account}\n")
               else:
                   f.write(line)
else:
    print("No Registry deployed.")
