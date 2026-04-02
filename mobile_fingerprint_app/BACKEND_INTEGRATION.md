# Backend Integration Guide

This document explains how to connect the mobile app with your existing Django backend.

## Prerequisites

- ✅ Backend running on Flask (`python backend/app.py`)
- ✅ Smart contracts deployed
- ✅ Ganache or blockchain node running
- ✅ Mobile app installed on Android device

## Configuration

### 1. Get Your Backend IP Address

**On Windows (where backend is running):**

```powershell
# Open PowerShell and run:
ipconfig

# Look for "IPv4 Address" (usually 192.168.x.x or 10.x.x.x)
# Example: 192.168.1.100
```

**On Mac/Linux:**

```bash
ifconfig

# Look for inet address (usually 192.168.x.x)
```

### 2. Update Mobile App Configuration

**Edit `.env` file in `mobile_fingerprint_app/`:**

```
EXPO_PUBLIC_BACKEND_URL=http://192.168.1.100:5000/api
```

Replace `192.168.1.100` with your actual backend IP.

### 3. Network Setup

**Ensure both devices are on the same WiFi:**

```
Phone: Connected to same WiFi network as backend computer
Computer: Backend running and accessible
```

**Test connectivity:**

```bash
# From mobile phone browser, try:
http://192.168.1.100:5000/api/health

# Should return:
# {"status": "ok"}
```

## API Endpoints Expected

The mobile app expects these endpoints from your backend:

### 1. Health Check

```
GET /api/health
Expected Response: {"status": "ok"}
```

### 2. Enrollment

```
POST /api/enroll
Content-Type: multipart/form-data

Request Body:
- name: String (user's full name)
- email: String (user's email)
- subjectId: String (unique identifier)
- fingerprintHash: String (SHA256 hash)
- file: Binary (JPEG image)
- type: String ("fingerprint")

Expected Response:
{
  "success": true,
  "message": "Enrollment successful",
  "data": {
    "subjectId": "USER_123...",
    "transactionHash": "0x123...",
    "blockNumber": 42,
    "templateCID": "QmXxxx..."
  }
}
```

### 3. Authentication

```
POST /api/authenticate
Content-Type: multipart/form-data

Request Body:
- subjectId: String (known identifier)
- fingerprintHash: String (SHA256 hash)
- file: Binary (JPEG image)
- type: String ("fingerprint")

Expected Response:
{
  "success": true,
  "message": "Authentication successful",
  "data": {
    "authenticated": true,
    "confidenceScore": 0.95,
    "transactionHash": "0x456...",
    "blockNumber": 43
  }
}
```

### 4. Blockchain Status

```
GET /api/blockchain/status

Expected Response:
{
  "connected": true,
  "network": "ganache",
  "blockNumber": 43
}
```

### 5. Subject Info

```
GET /api/subjects/{subjectId}

Expected Response:
{
  "subjectId": "USER_123...",
  "enrolledAt": 1234567890,
  "enrollmentCount": 1,
  "lastAuth": 1234567900
}
```

### 6. Auth Logs

```
GET /api/auth-logs?subjectId={subjectId}

Expected Response:
[
  {
    "subjectId": "USER_123...",
    "success": true,
    "timestamp": 1234567900,
    "transactionHash": "0x456..."
  }
]
```

## Backend Verification

### Step 1: Check Backend is Running

```powershell
# Check if Flask is listening on port 5000
netstat -ano | findstr :5000

# Or visit in browser:
http://localhost:5000/api/health
```

### Step 2: Check Contracts are Deployed

```python
# Run from backend directory:
python
>>> from web3 import Web3
>>> web3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
>>> web3.eth.accounts[0]
# Should return account address
```

### Step 3: Verify Smart Contract Addresses

```python
# Check if contract address is set
import os
from dotenv import load_dotenv
load_dotenv()

print(os.environ.get('FINGERPRINT_REGISTRY_ADDRESS'))
# Should print contract address like 0x123...
```

## Troubleshooting

### Issue: "Backend connection failed" in mobile app

**Check 1**: Backend is running

```powershell
# Terminal where backend is running should show:
# Running on http://127.0.0.1:5000
```

**Check 2**: Correct IP in `.env`

```
# Get correct IP:
ipconfig | grep "IPv4 Address"

# Update .env:
EXPO_PUBLIC_BACKEND_URL=http://192.168.1.100:5000/api
```

**Check 3**: Network connectivity

```powershell
# From backend computer:
ping 192.168.x.x  # Phone's IP

# From phone (using terminal app):
ping 192.168.1.100  # Backend's IP
```

**Check 4**: Firewall

```powershell
# Allow port 5000 through Windows Firewall:
# Settings > Firewall > Allow app through firewall
# OR disable firewall temporarily for testing
```

**Check 5**: CORS Configuration

```python
# In backend/app.py, ensure CORS is enabled:
from flask_cors import CORS
CORS(app)
```

### Issue: "Enrollment failed" with 500 error

**Check**:

- Contract is deployed (`npm run migrate`)
- Contract address is correct in `.env`
- Gas value is sufficient
- Ganache has enough ether for transactions

```python
# Check account balance:
web3.eth.get_balance(web3.eth.accounts[0])
# Should be > 0
```

### Issue: Fingerprint capture returns empty

**Check**:

- `/fingerprint/capture` endpoint in backend
- Backend has fingerprint engine loaded
- USB scanner connected (if external sensor)
- Sensor permissions granted in mobile app

## Testing Flow

### Complete Integration Test

```
1. Mobile App Enrollment Test
   ↓
   a) Open app > Enroll tab
   b) Enter name, email
   c) Place finger on sensor
   d) Confirm enrollment
   e) Check response in backend logs
   f) Verify transaction on blockchain: http://localhost:7545 (Ganache)
   ↓
2. Mobile App Authentication Test
   ↓
   a) Open app > Authenticate tab
   b) Enter Subject ID (from enrollment)
   c) Place finger on sensor
   d) Verify against blockchain records
   e) Check confidence score
   ↓
3. Backend Verification
   ↓
   a) Query contract directly:
      from web3 import Web3
      contract.functions.getSubject(subject_id).call()
   b) Check all enrollments stored
   c) Verify transaction hashes
```

## Performance Tuning

### If App is Slow:

1. **Reduce Image Quality** (in `src/services/biometricService.ts`)

```typescript
// Change JPEG quality from 0.92 to 0.75
.toDataURL("image/jpeg", 0.75)
```

2. **Increase Backend Timeout** (in `src/services/apiClient.ts`)

```typescript
// Increase from 30000 to 60000ms
timeout: 60000;
```

3. **Enable Caching** (in backend)

```python
@app.after_request
def set_cache_headers(response):
    response.cache_control.max_age = 3600
    return response
```

## Production Deployment

### Mobile App

```bash
# Build production APK
npm run build:apk

# Install on device
adb install blockchain-fingerprint-mobile.apk
```

### Backend

```bash
# Use production WSGI server
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 backend.app:app
```

### Security Checklist

- [ ] Change API endpoint to HTTPS (use ngrok for testing)
- [ ] Enable authentication/API keys
- [ ] Validate input data in all endpoints
- [ ] Set CORS restrictions to specific domains
- [ ] Use environment variables for secrets
- [ ] Enable rate limiting
- [ ] Set up monitoring and logging

## Support & Debugging

### Enable Verbose Logging

**Mobile App:**

```typescript
// In src/services/apiClient.ts
// Already has console.log statements
// Check browser DevTools or Android Studio logs
```

**Backend:**

```python
# In backend/app.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Common Error Codes

| Code         | Meaning             | Solution                      |
| ------------ | ------------------- | ----------------------------- |
| ECONNREFUSED | Backend not running | Start backend service         |
| ETIMEDOUT    | Network unreachable | Check firewall/network        |
| 401          | Unauthorized        | Check API key/auth            |
| 404          | Endpoint not found  | Check backend version         |
| 500          | Server error        | Check backend logs            |
| 422          | Invalid data        | Check fingerprint hash format |

---

**Last Updated**: April 2, 2026
**Status**: ✅ Ready for Integration
