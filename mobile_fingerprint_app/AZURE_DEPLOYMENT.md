# 🚀 Azure Deployment Guide - Mobile Fingerprint App

## ✅ Current Azure Status

### Resource Group: **BiometricIdentity-RG** (Southeast Asia)

| Resource                  | Type                       | Status         |
| ------------------------- | -------------------------- | -------------- |
| **biometric-backend-app** | Container App              | ✅ **Running** |
| **Blockchain**            | Container Registry         | ✅ Ready       |
| **biometricfe2026**       | Storage Account (V2)       | ✅ Ready       |
| **biometric-db-123**      | PostgreSQL Flex Server     | ✅ Ready       |
| **biomongo20746**         | Cosmos DB (MongoDB)        | ✅ Ready       |
| **biometric-ca-env**      | Container Apps Environment | ✅ Ready       |
| **biometric-law**         | Log Analytics              | ✅ Ready       |

---

## 🎯 Deployment Options for Mobile App

### **Option 1: Build APK & Host on Azure Storage (RECOMMENDED)**

- ✅ Simplest implementation
- ✅ No additional resources needed
- ✅ Instant download link
- ⏱️ Time: 20-30 minutes
- 💰 Cost: Already covered by storage account

**Steps:**

```bash
# 1. Build APK locally
cd mobile_fingerprint_app
npm run build:apk

# 2. Upload to Azure Storage
az storage blob upload-batch \
  --account-name biometricfe2026 \
  --destination apk \
  --source ./dist/

# 3. Generate download link (valid 365 days)
az storage blob generate-sas \
  --account-name biometricfe2026 \
  --container-name apk \
  --name "blockchain-fingerprint-mobile.apk" \
  --permissions racwd \
  --expiry $(date -u -d "+365 days" +%Y-%m-%dT%H:%M:%SZ)
```

---

### **Option 2: CI/CD with GitHub Actions (AUTOMATED)**

- ✅ Automated builds on every push
- ✅ APK auto-uploaded to Azure Storage
- ✅ Version management
- ⏱️ Time: 45-60 minutes setup
- 💰 Cost: Free (GitHub Actions included)

**Setup:**
Create `.github/workflows/deploy.yml`:

```yaml
name: Build & Deploy Mobile App

on:
  push:
    branches: [main]
    paths:
      - "mobile_fingerprint_app/**"

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node
        uses: actions/setup-node@v3
        with:
          node-version: 18

      - name: Install Expo CLI
        run: npm install -g eas-cli

      - name: Build APK
        working-directory: mobile_fingerprint_app
        run: |
          npm install
          npm run build:apk

      - name: Upload to Azure Storage
        uses: azure/CLI@v1
        with:
          azcliversion: latest
          inlineScript: |
            az storage blob upload \
              --account-name biometricfe2026 \
              --container-name apk \
              --name "blockchain-fingerprint-${{ github.run_id }}.apk" \
              --file dist/*.apk
```

---

### **Option 3: Azure DevOps Pipeline (ENTERPRISE)**

- ✅ Full integration with Azure
- ✅ Advanced deployment gates
- ✅ Multiple environments
- ⏱️ Time: 1-2 hours setup
- 💰 Cost: Free tier available

---

### **Option 4: Azure Container Apps with APK Server (ADVANCED)**

- ✅ Serve APK from web interface
- ✅ Download statistics & tracking
- ✅ Version management dashboard
- ⏱️ Time: 2-3 hours setup
- 💰 Cost: ~$40/month additional

**Deploy Node.js server:**

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package.json .
RUN npm install
COPY server.js .
EXPOSE 3000
CMD ["node", "server.js"]
```

---

## 🚀 QUICK START - Option 1 (Recommended)

### **Step 1: Build APK on Your Machine**

```bash
cd mobile_fingerprint_app

# Install dependencies
npm install

# Build APK
npm run build:apk

# Monitor the build
# Opens browser with build status
# Wait 5-10 minutes for build to complete
```

### **Step 2: Download APK**

When build completes, you'll get a download link.

```
Example: https://d.expo.dev/...
```

### **Step 3: Upload to Azure Storage**

```powershell
# Get storage account key
$storageKey = az storage account keys list \
  --resource-group BiometricIdentity-RG \
  --account-name biometricfe2026 \
  --query "[0].value" -o tsv

# Create 'apk' container if it doesn't exist
az storage container create \
  --account-name biometricfe2026 \
  --account-key $storageKey \
  --name apk

# Upload APK
$apkPath = "blockchain-fingerprint-mobile.apk"
az storage blob upload \
  --account-name biometricfe2026 \
  --account-key $storageKey \
  --container-name apk \
  --name $apkPath \
  --file $apkPath

# Generate public download link (365 days)
$endTime = (Get-Date).AddDays(365).ToString("yyyy-MM-ddTHH:mm:ssZ")
az storage blob generate-sas \
  --account-name biometricfe2026 \
  --account-key $storageKey \
  --container-name apk \
  --name $apkPath \
  --permissions racwd \
  --expiry $endTime
```

### **Step 4: Share Download Link**

The SAS URL will look like:

```
https://biometricfe2026.blob.core.windows.net/apk/blockchain-fingerprint-mobile.apk?sv=2021-06-08&ss=b&...
```

Users can:

1. Open link in phone browser
2. Download APK
3. Install on Android device

---

## 🔗 Backend URL Configuration

For mobile app to connect to your Azure backend:

```bash
# Get backend URL
az containerapp show \
  --resource-group BiometricIdentity-RG \
  --name biometric-backend-app \
  --query "properties.latestRevisionFqdn" -o tsv
```

**Update mobile app `.env`:**

```
EXPO_PUBLIC_BACKEND_URL=https://[OUTPUT_FROM_ABOVE]/api
```

---

## 📊 Deployment Checklist

### Pre-Deployment

- [ ] Azure CLI installed
- [ ] Logged into Azure (`az login`)
- [ ] Correct subscription selected
- [ ] Mobile app code is final
- [ ] `.env` configured with correct backend URL

### Deployment

- [ ] APK built successfully
- [ ] Storage account ready
- [ ] APK uploaded to Azure
- [ ] Download link tested on phone
- [ ] APK installs correctly

### Post-Deployment

- [ ] Test enrollment flow
- [ ] Test authentication flow
- [ ] Test blockchain integration
- [ ] Monitor backend logs for errors
- [ ] Share download link with users

---

## 🔄 Update Flow (After Initial Deployment)

### For Quick Updates

```powershell
# Build new APK
npm run build:apk

# Upload with version tag
az storage blob upload \
  --account-name biometricfe2026 \
  --container-name apk \
  --name "blockchain-fingerprint-v1.1.apk" \
  --file "blockchain-fingerprint-mobile.apk"

# Generate new SAS link
az storage blob generate-sas \
  --account-name biometricfe2026 \
  --container-name apk \
  --name "blockchain-fingerprint-v1.1.apk" \
  --permissions racwd \
  --expiry $(date -u -d "+365 days" +%Y-%m-%dT%H:%M:%SZ)
```

---

## 🔐 Security Checklist

- [ ] HTTPS enabled for all connections
- [ ] Storage account firewall configured
- [ ] SAS tokens have expiration date
- [ ] Backend API requires authentication
- [ ] Private container for builds (if needed)
- [ ] Monitor unauthorized access logs

---

## 📈 Monitoring & Logs

### View Backend Logs

```bash
az containerapp logs show \
  --resource-group BiometricIdentity-RG \
  --name biometric-backend-app
```

### Monitor Storage Access

```bash
# Log Analytics query
az monitor log-analytics workspace list \
  --resource-group BiometricIdentity-RG
```

### Check App Performance

```bash
# Application Insights query (if configured)
az monitor app-insights component show \
  --resource-group BiometricIdentity-RG
```

---

## 💰 Cost Estimate

| Service                  | Usage       | Monthly Cost |
| ------------------------ | ----------- | ------------ |
| Storage Account          | 100 MB APKs | < $1         |
| Container Apps (backend) | Running     | ~$37         |
| PostgreSQL               | Flex Server | ~$30         |
| Cosmos DB                | Shared tier | ~$25         |
| **Total**                |             | **~$92+**    |

---

## 🆘 Troubleshooting

### Issue: "APK Build Failed"

**Solution:**

```bash
# Clear cache and rebuild
npm run build:apk --reset-cache

# Check Node version (need 16+)
node --version

# Update Expo CLI
npm install -g expo-cli@latest
```

### Issue: "Upload to Storage Failed"

**Solution:**

```bash
# Verify auth
az account show

# Check storage account exists
az storage account list --query "[].name"

# Check storage key
az storage account keys list \
  --resource-group BiometricIdentity-RG \
  --account-name biometricfe2026
```

### Issue: "APK Download Link Not Working"

**Solution:**

```bash
# Regenerate SAS token
az storage blob generate-sas \
  --account-name biometricfe2026 \
  --container-name apk \
  --name "blockchain-fingerprint-mobile.apk" \
  --permissions r \  # read-only
  --expiry $(date -u -d "+7 days" +%Y-%m-%dT%H:%M:%SZ)
```

---

## 📞 Next Steps

1. **Choose deployment option** (Option 1 recommended)
2. **Build APK locally**
3. **Upload to Azure Storage**
4. **Test download link**
5. **Share with users**
6. **Monitor for issues**

---

**Last Updated**: April 2, 2026
**Status**: ✅ Ready for Deployment
