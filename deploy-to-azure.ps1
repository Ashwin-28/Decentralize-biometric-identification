#!/usr/bin/env pwsh
<#
.SYNOPSIS
Deploy Blockchain Fingerprint Mobile App to Azure Storage

.DESCRIPTION
This script builds the mobile app APK and deploys it to Azure Storage for distribution

.PARAMETER ResourceGroup
Name of the Azure resource group (default: BiometricIdentity-RG)

.PARAMETER StorageAccount
Name of the storage account (default: biometricfe2026)

.PARAMETER Version
Version tag for the APK (default: auto-generated from date)

.EXAMPLE
.\deploy-to-azure.ps1
.\deploy-to-azure.ps1 -Version "v1.0.0"
#>

param(
    [string]$ResourceGroup = "BiometricIdentity-RG",
    [string]$StorageAccount = "biometricfe2026",
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"

# Colors for output
$Green = @{ ForegroundColor = 'Green' }
$Yellow = @{ ForegroundColor = 'Yellow' }
$Red = @{ ForegroundColor = 'Red' }

Write-Host "🚀 Blockchain Fingerprint Mobile App - Azure Deployment" @Yellow
Write-Host "=========================================================`n" @Yellow

# Check if Azure CLI is installed
Write-Host "✓ Checking prerequisites..." @Green
try {
    $azVersion = az --version | Select-Object -First 1
    Write-Host "  ✓ Azure CLI: $azVersion"
}
catch {
    Write-Host "  ✗ Azure CLI not found. Install from: https://aka.ms/azure-cli" @Red
    exit 1
}

# Check if logged in
try {
    $account = az account show --query "name" -o tsv
    Write-Host "  ✓ Logged in as: $account"
}
catch {
    Write-Host "  ✗ Not logged into Azure. Run: az login" @Red
    exit 1
}

# Check if Node.js is installed
try {
    $nodeVersion = node --version
    Write-Host "  ✓ Node.js: $nodeVersion"
}
catch {
    Write-Host "  ✗ Node.js not found. Install from: https://nodejs.org" @Red
    exit 1
}

Write-Host "`n✓ Prerequisites check passed!`n" @Green

# Check if resource group exists
Write-Host "✓ Checking Azure resources..."
try {
    $rg = az group show --name $ResourceGroup --query "name" -o tsv
    Write-Host "  ✓ Resource Group: $rg (Southeast Asia)"
}
catch {
    Write-Host "  ✗ Resource group not found: $ResourceGroup" @Red
    exit 1
}

# Check if storage account exists
try {
    $sa = az storage account show `
        --resource-group $ResourceGroup `
        --name $StorageAccount `
        --query "name" -o tsv
    Write-Host "  ✓ Storage Account: $sa"
}
catch {
    Write-Host "  ✗ Storage account not found: $StorageAccount" @Red
    exit 1
}

Write-Host "`n✓ Azure resources verified!`n" @Green

# Get storage account key
Write-Host "✓ Getting storage credentials..."
$storageKey = az storage account keys list `
    --resource-group $ResourceGroup `
    --account-name $StorageAccount `
    --query "[0].value" -o tsv
Write-Host "  ✓ Storage key retrieved`n" @Green

# Ensure mobile app directory exists
if (!(Test-Path "mobile_fingerprint_app/package.json")) {
    Write-Host "✗ mobile_fingerprint_app directory not found!" @Red
    exit 1
}

# Change to mobile app directory
Push-Location "mobile_fingerprint_app"

# Install dependencies
Write-Host "✓ Installing dependencies..." @Green
npm install --silent
Write-Host "  ✓ Dependencies installed`n" @Green

# Check EAS CLI
Write-Host "✓ Checking EAS CLI..."
try {
    $easVersion = npx eas-cli --version
    Write-Host "  ✓ EAS CLI: $easVersion"
}
catch {
    Write-Host "  ⚠ Installing EAS CLI..."
    npm install -g eas-cli
    $easVersion = eas --version
    Write-Host "  ✓ EAS CLI installed: $easVersion"
}

# Ensure EAS login is available for cloud builds
try {
    $who = npx eas-cli whoami 2>&1
    if ($LASTEXITCODE -ne 0 -or $who -match "Not logged in") {
        Write-Host "  ✗ Not logged into EAS. Run: npx eas-cli login" @Red
        Pop-Location
        exit 1
    }
    Write-Host "  ✓ EAS Account: $who"
}
catch {
    Write-Host "  ✗ Could not verify EAS login. Run: npx eas-cli login" @Red
    Pop-Location
    exit 1
}

# Generate version tag if not provided
if ([string]::IsNullOrEmpty($Version)) {
    $Version = "v$(Get-Date -Format 'yyyyMMdd.HHmm')"
}

Write-Host "`n✓ Building APK with EAS (this may take 10-20 minutes)...`n" @Yellow

# Build APK using EAS cloud build
Write-Host "📱 Starting EAS Android build..."
$buildOutput = npx eas-cli build --platform android --profile preview --wait --json 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Build failed. Check the logs above." @Red
    Pop-Location
    exit 1
}

# Parse JSON output from EAS
$buildInfo = $null
try {
    $buildInfo = ($buildOutput | Out-String) | ConvertFrom-Json
}
catch {
    Write-Host "⚠ Could not parse EAS output JSON. Check EAS dashboard: https://expo.dev/accounts" @Yellow
    Pop-Location
    exit 1
}

$apkUrl = $buildInfo.artifacts.buildUrl

if ([string]::IsNullOrEmpty($apkUrl)) {
    Write-Host "⚠ Build finished but APK URL was not returned. Check EAS dashboard." @Yellow
    Pop-Location
    exit 1
}

# Download APK from EAS artifact URL
Write-Host "`n✓ Build complete! Downloading APK...`n" @Green

$apkFile = "blockchain-fingerprint-mobile-$Version.apk"
Write-Host "  Downloading: $apkFile"
Invoke-WebRequest -Uri $apkUrl -OutFile $apkFile -Verbose:$false

if (!(Test-Path $apkFile)) {
    Write-Host "✗ APK download failed!" @Red
    Pop-Location
    exit 1
}

$apkSize = (Get-Item $apkFile).Length / 1MB
Write-Host "  ✓ APK downloaded: $apkFile ($($apkSize.ToString('F1')) MB)`n" @Green

Pop-Location  # Return to original directory

# Create Azure Storage container if it doesn't exist
Write-Host "✓ Preparing Azure Storage...`n" @Green
try {
    az storage container create `
        --account-name $StorageAccount `
        --account-key $storageKey `
        --name apk 2>&1 | Out-Null
    Write-Host "  ✓ Container 'apk' ready"
}
catch {
    # Container might already exist
    Write-Host "  ✓ Container 'apk' verified"
}

# Upload APK to Azure Storage
Write-Host "  📤 Uploading to Azure Storage..."
az storage blob upload `
    --account-name $StorageAccount `
    --account-key $storageKey `
    --container-name apk `
    --name $apkFile `
    --file "mobile_fingerprint_app/$apkFile" `
    --no-progress | Out-Null

Write-Host "  ✓ APK uploaded to Azure Storage`n" @Green

# Generate SAS URL with 365-day expiration
Write-Host "✓ Generating download link...`n" @Green
$endTime = (Get-Date).AddDays(365).ToString("yyyy-MM-ddTHH:mm:ssZ")

$sasUrl = az storage blob generate-sas `
    --account-name $StorageAccount `
    --account-key $storageKey `
    --container-name apk `
    --name $apkFile `
    --permissions racwd `
    --expiry $endTime `
    --output tsv

$downloadUrl = "https://${StorageAccount}.blob.core.windows.net/apk/${apkFile}?${sasUrl}"

Write-Host "✅ DEPLOYMENT COMPLETE!`n" @Green
Write-Host "=" * 70
Write-Host "`n📲 DOWNLOAD LINK (Valid for 365 days):`n" @Yellow
Write-Host $downloadUrl
Write-Host "`n" @Green

# Create a QR code link (using QR.io service)
$qrUrl = "https://qr.io/?u=" + [System.Web.HttpUtility]::UrlEncode($downloadUrl)
Write-Host "📱 QR Code: $qrUrl`n" @Yellow

Write-Host "=" * 70
Write-Host "`n✓ Users can now:
  1. Open the download link on their phone
  2. Download the APK
  3. Enable 'Unknown Sources' in Settings
  4. Install the APK
  5. Open app and configure backend URL`n" @Green

Write-Host "📊 App Information:`n" @Green
Write-Host "  App Name: Biometric Wallet"
Write-Host "  Version: $Version"
Write-Host "  Package: com.biometric.fingerprint"
Write-Host "  Min Android: API 33"
Write-Host "  File Size: $($apkSize.ToString('F1')) MB`n" @Green

Write-Host "🔗 Backend Configuration:`n" @Green
$backendUrl = az containerapp show `
    --resource-group $ResourceGroup `
    --name biometric-backend-app `
    --query "properties.latestRevisionFqdn" -o tsv

Write-Host "  Backend URL: https://$backendUrl/api`n" @Green

Write-Host "📝 Next steps:`n" @Green
Write-Host "  1. Share download link with users"
Write-Host "  2. Users install APK on their Android phone"
Write-Host "  3. Configure app with backend URL (via Settings)"
Write-Host "  4. Test enrollment and authentication flows"
Write-Host "  5. Monitor backend logs: az containerapp logs show --resource-group $ResourceGroup --name biometric-backend-app`n" @Green

Write-Host "🎉 Your mobile app is now deployed to Azure!`n" @Yellow
