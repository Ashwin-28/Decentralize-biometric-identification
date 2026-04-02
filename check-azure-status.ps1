#!/usr/bin/env pwsh
<#
.SYNOPSIS
Check Azure resources status and deployment readiness

.DESCRIPTION
Verifies that all resources in BiometricIdentity-RG are running

.EXAMPLE
.\check-azure-status.ps1
#>

$ErrorActionPreference = "Continue"

# Colors
$Green = @{ ForegroundColor = 'Green' }
$Yellow = @{ ForegroundColor = 'Yellow' }
$Red = @{ ForegroundColor = 'Red' }
$Blue = @{ ForegroundColor = 'Cyan' }

Write-Host "`n🔍 AZURE RESOURCES STATUS CHECK" @Blue
Write-Host "================================`n" @Blue

$rg = "BiometricIdentity-RG"

# Check subscription
Write-Host "📊 Subscription:" @Yellow
$sub = az account show --query "{name: name, id: id}" -o json | ConvertFrom-Json
Write-Host "  ✓ $($sub.name)" @Green

# List all resources
Write-Host "`n📦 Resources in $rg:" @Yellow

$resources = @(
    @{name="biometric-backend-app"; type="Container Apps"; command="az containerapp show --resource-group $rg --name biometric-backend-app --query 'properties.provisioningState' -o tsv"},
    @{name="Blockchain"; type="Container Registry"; command="az acr show --resource-group $rg --name Blockchain --query 'provisioningState' -o tsv"},
    @{name="biometric-db-123"; type="PostgreSQL"; command="az postgres flexible-server show --resource-group $rg --name biometric-db-123 --query 'state' -o tsv"},
    @{name="biometricfe2026"; type="Storage"; command="az storage account show --resource-group $rg --name biometricfe2026 --query 'provisioningState' -o tsv"},
    @{name="biomongo20746"; type="Cosmos DB"; command="az cosmosdb show --resource-group $rg --name biomongo20746 --query 'provisioningState' -o tsv"}
)

$allHealthy = $true

foreach ($resource in $resources) {
    try {
        $status = Invoke-Expression $resource.command 2>&1
        $statusColor = if ($status -match "Succeeded|Running|Available") { $Green } else { $Yellow }
        Write-Host "  ✓ $($resource.name) ($($resource.type)): $status" @statusColor
    }
    catch {
        Write-Host "  ✗ $($resource.name) ($($resource.type)): Error" @Red
        $allHealthy = $false
    }
}

# Check backend connectivity
Write-Host "`n🔗 Backend Connectivity:" @Yellow
try {
    $fqdn = az containerapp show --resource-group $rg --name biometric-backend-app --query "properties.latestRevisionFqdn" -o tsv
    $health = curl -s -m 5 "https://$fqdn/api/health" -o /dev/null -w "%{http_code}"
    
    if ($health -eq "200") {
        Write-Host "  ✓ Backend Health Check: Healthy (HTTP $health)" @Green
        Write-Host "  ✓ Backend URL: https://$fqdn/api" @Green
    }
    else {
        Write-Host "  ⚠ Backend Health Check: HTTP $health" @Yellow
    }
}
catch {
    Write-Host "  ⚠ Could not reach backend (may be cold start)" @Yellow
}

# Check storage
Write-Host "`n💾 Storage Configuration:" @Yellow
try {
    $containers = az storage container list --account-name biometricfe2026 --query "[].name" -o tsv --auth-mode key --account-key (az storage account keys list --resource-group $rg --account-name biometricfe2026 --query "[0].value" -o tsv) 2>&1
    Write-Host "  ✓ Storage Containers: $([string]::Join(", ", ($containers | Where-Object {$_})))" @Green
}
catch {
    Write-Host "  ⚠ Could not list storage containers" @Yellow
}

# Summary
Write-Host "`n" @Blue
if ($allHealthy) {
    Write-Host "✅ ALL SYSTEMS OPERATIONAL" @Green
    Write-Host "`nYour Azure environment is ready for mobile app deployment!`n" @Green
}
else {
    Write-Host "⚠️ Some resources may need attention" @Yellow
    Write-Host "`nCheck the status above and restart any failed resources.`n" @Yellow
}

# Deployment instructions
Write-Host "🚀 NEXT STEPS:" @Blue
Write-Host "  1. Run: ./deploy-to-azure.ps1" @Yellow
Write-Host "  2. Follow the prompts to build and upload APK" @Yellow
Write-Host "  3. Share the generated download link with users" @Yellow
Write-Host "`n"
