# ==============================================================================
# PowerShell Script to Configure GCP for GitHub Actions Deployment (Idempotent)
# ==============================================================================
# This script is now idempotent: it checks for existing resources before creating them.
# 1. Defines configuration variables.
# 2. Ensures the dedicated Service Account exists.
# 3. Grants all necessary IAM roles to the Service Account.
# 4. Sets up Workload Identity Federation.
# 5. Outputs the exact values needed for your GitHub Secrets.
# ==============================================================================

# --- Step 1: Configuration ---
$projectId = "fraud-digest-app-v2-469310"
$serviceAccountName = "github-actions-deployer"
$repoPath = "mayafudimaxionym/The-Fraud-Digest-Weekly-app"
$poolName = "github-pool"
$providerName = "github-provider"

$serviceAccountEmail = "$($serviceAccountName)@$($projectId).iam.gserviceaccount.com"

# --- Set the active project for all subsequent gcloud commands ---
Write-Host "Setting active project to '$($projectId)'..." -ForegroundColor Yellow
gcloud config set project $projectId

# --- Step 2: Ensure Service Account Exists ---
Write-Host "`n[TASK 1/4] Checking for Service Account '$($serviceAccountName)'..." -ForegroundColor Cyan
gcloud iam service-accounts describe $serviceAccountEmail --project=$projectId > $null 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "Service Account '$($serviceAccountEmail)' already exists. Skipping creation." -ForegroundColor Green
} else {
    Write-Host "Service Account not found. Creating it now..." -ForegroundColor Yellow
    gcloud iam service-accounts create $serviceAccountName `
      --display-name="GitHub Actions Deployer" `
      --project=$projectId
    Write-Host "Service Account created successfully." -ForegroundColor Green
}

# --- Step 3: Grant IAM Roles ---
Write-Host "`n[TASK 2/4] Granting necessary IAM roles to Service Account..." -ForegroundColor Cyan
$roles = @(
    "roles/run.admin",
    "roles/artifactregistry.admin",
    "roles/cloudbuild.builds.editor",
    "roles/iam.serviceAccountUser",
    "roles/pubsub.admin"
)
foreach ($role in $roles) {
    Write-Host "  - Ensuring role: $role"
    # This command is additive and won't cause errors if the binding already exists.
    gcloud projects add-iam-policy-binding $projectId `
      --member="serviceAccount:$($serviceAccountEmail)" `
      --role="$role" `
      --condition=null > $null 2>&1
}
Write-Host "All roles have been granted/verified." -ForegroundColor Green

# --- Step 4: Configure Workload Identity Federation ---
Write-Host "`n[TASK 3/4] Configuring Workload Identity Federation..." -ForegroundColor Cyan

Write-Host "  - Enabling required APIs..."
gcloud services enable iamcredentials.googleapis.com --project=$projectId

Write-Host "  - Ensuring Workload Identity Pool '$($poolName)' exists..."
gcloud iam workload-identity-pools describe $poolName --location="global" --project=$projectId > $null 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "Workload Identity Pool '$($poolName)' already exists. Skipping creation."
} else {
    gcloud iam workload-identity-pools create $poolName `
        --location="global" `
        --display-name="GitHub Actions Pool" `
        --project=$projectId
}

Write-Host "  - Ensuring OIDC Provider '$($providerName)' exists..."
gcloud iam workload-identity-pools providers describe $providerName --location="global" --workload-identity-pool=$poolName --project=$projectId > $null 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "OIDC Provider '$($providerName)' already exists. Skipping creation."
} else {
    gcloud iam workload-identity-pools providers create-oidc $providerName `
        --location="global" `
        --workload-identity-pool=$poolName `
        --issuer-uri="https://token.actions.githubusercontent.com" `
        --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" `
        --project=$projectId
}

Write-Host "  - Linking GitHub repository to the Service Account..."
$projectNumber = $(gcloud projects describe $projectId --format='value(projectNumber)')
$principal = "principalSet://iam.googleapis.com/projects/$($projectNumber)/locations/global/workloadIdentityPools/$($poolName)/subject/repo:$($repoPath):ref:refs/heads/main"
# This command is also additive and safe to re-run.
gcloud iam service-accounts add-iam-policy-binding $serviceAccountEmail `
    --role="roles/iam.workloadIdentityUser" `
    --member=$principal `
    --project=$projectId > $null 2>&1
Write-Host "Workload Identity Federation configured successfully." -ForegroundColor Green


# --- Step 5: Final Output ---
Write-Host "`n[TASK 4/4] Retrieving values for GitHub Secrets..." -ForegroundColor Cyan
$wifProvider = $(gcloud iam workload-identity-pools providers describe $providerName `
    --location="global" `
    --workload-identity-pool=$poolName `
    --format="value(name)" `
    --project=$projectId)

Write-Host "==============================================================================" -ForegroundColor Yellow
Write-Host "✅ SETUP COMPLETE. Create/update the following secrets in your GitHub repository:"
Write-Host "   Go to: Settings > Secrets and variables > Actions > New repository secret"
Write-Host "------------------------------------------------------------------------------"

Write-Host "`n1. GCP_PROJECT_ID" -ForegroundColor White
Write-Host "   Value: " -NoNewline; Write-Host "$($projectId)" -ForegroundColor Magenta

Write-Host "`n2. GCP_SA_EMAIL" -ForegroundColor White
Write-Host "   Value: " -NoNewline; Write-Host "$($serviceAccountEmail)" -ForegroundColor Magenta

Write-Host "`n3. GCP_WIF_PROVIDER" -ForegroundColor White
Write-Host "   Value: " -NoNewline; Write-Host "$($wifProvider)" -ForegroundColor Magenta

Write-Host "==============================================================================" -ForegroundColor Yellow
Write-Host "`nYou can now proceed to deploy your application using GitHub Actions!" -ForegroundColor Green

# ==============================================================================
# Note: Remember to run this script in an environment where the gcloud CLI is installed and authenticated.
# ==============================================================================
# ==============================================================================
# End of Script
