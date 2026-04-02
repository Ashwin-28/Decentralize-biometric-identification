# 🚀 Biometric Identity - Azure Deployment Script
# Run this from your terminal in the backend/ folder

# CONFIGURATION (EDIT THESE AFTER CREATING IN AZURE PORTAL)
# ---------------------------------------------------------
$ACR_NAME = "Blockchain"      # Example: your ACR name
$WEBAPP_NAME = "biometric-backend-app" # Example: your App Service name
$RESOURCE_GROUP = "BiometricIdentity-RG"
# ---------------------------------------------------------

Write-Host "--- 🏗️ Starting Deployment to Azure ---" -ForegroundColor Cyan

# 1. Check for Login
Write-Host "[1/5] Checking Azure Login..." -ForegroundColor Yellow
$loginStatus = az account show --query "user.name" -o tsv
if ($null -eq $loginStatus) {
    Write-Host "Error: You are not logged in to Azure." -ForegroundColor Red
    Write-Host "Please run 'az login' in your browser first, then try this script again."
    exit
}

# 2. Login to Container Registry
Write-Host "[2/5] Logging into Azure Container Registry ($ACR_NAME)..." -ForegroundColor Yellow
az acr login --name $ACR_NAME

# 3. Build & Tag Docker Image
Write-Host "[3/5] Building Docker Image (this may take 5-10 minutes for AI libraries)..." -ForegroundColor Yellow
docker build -t "$($ACR_NAME).azurecr.io/backend:latest" .

# 4. Push to Azure
Write-Host "[4/5] Pushing Image to Azure... (uploading ~2-3GB of AI data)" -ForegroundColor Yellow
docker push "$($ACR_NAME).azurecr.io/backend:latest"

# 5. Connect App Service to Image
Write-Host "[5/5] Connecting Web App ($WEBAPP_NAME) to new image..." -ForegroundColor Yellow
az webapp config container set --name $WEBAPP_NAME --resource-group $RESOURCE_GROUP --docker-custom-image-name "$($ACR_NAME).azurecr.io/backend:latest" --docker-registry-server-url "https://$($ACR_NAME).azurecr.io"

Write-Host "--- 🎉 DEPLOYMENT COMPLETE! ---" -ForegroundColor Green
Write-Host "Your backend is now live! Remember to set your .env settings in the Azure Configuration portal."
