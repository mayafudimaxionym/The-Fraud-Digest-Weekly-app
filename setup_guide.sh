#!/bin/bash
# ==============================================================================
# COOKBOOK: Deploying a secure Cloud Run service with IAP and CI/CD
# ==============================================================================
# This script documents all the necessary steps to set up the infrastructure
# and CI/CD pipeline for the application.

# --- Step 0: Configuration ---
# Fill these variables before running the script for a new project.

# --- Project Configuration ---
export NEW_PROJECT_NAME="Fraud Digest App V2"
export NEW_PROJECT_ID="fraud-digest-app-v2-469310" # Must be unique globally
export BILLING_ACCOUNT_ID="015A12-204E88-9F704C"
export REGION="europe-west1"
export ORGANIZATION_ID="303337513280"
export CUSTOMER_ID="C00ueh1pc"

# --- Application Configuration ---
export GITHUB_REPO="mayafudimaxionym/The-Fraud-Digest-Weekly-app"
export SERVICE_NAME="fraud-digest-weekly-app"
export DOMAIN_NAME="frapp.axionym.com"

# --- Resource Names (can be customized) ---
export AR_REPO_NAME="fraud-digest-repo"
export IMAGE_NAME="the-fraud-digest-weekly-app"
export CI_SERVICE_ACCOUNT="github-actions-deployer"
export NEG_NAME="fraud-digest-neg"
export BACKEND_SERVICE_NAME="fraud-digest-backend"
export URL_MAP_NAME="fraud-digest-url-map"
export SSL_CERT_NAME="fraud-digest-ssl-cert"
export HTTPS_PROXY_NAME="fraud-digest-https-proxy"
export IP_NAME="fraud-digest-ip"
export FW_RULE_NAME="fraud-digest-forwarding-rule"

# --- User Configuration ---
export ADMIN_USER_EMAIL="maya.fudim@axionym.com"


# ==============================================================================
# SECTION 1: CI/CD SETUP (Workload Identity Federation)
# ==============================================================================
echo "--- Section 1: Setting up CI/CD ---"

# 1.1. Set the project context
gcloud config set project ${NEW_PROJECT_ID}

# 1.2. Enable required APIs for CI/CD
gcloud services enable iamcredentials.googleapis.com --project=${NEW_PROJECT_ID}

# 1.3. Create the CI/CD service account
gcloud iam service-accounts create ${CI_SERVICE_ACCOUNT} \
  --project=${NEW_PROJECT_ID} \
  --display-name="GitHub Actions Deployer"

# 1.4. Grant CI/CD service account necessary roles
# 1.4.1. Artifact Registry Writer
gcloud artifacts repositories add-iam-policy-binding ${AR_REPO_NAME} \
  --location=${REGION} \
  --project=${NEW_PROJECT_ID} \
  --member="serviceAccount:${CI_SERVICE_ACCOUNT}@${NEW_PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

# 1.4.2. Cloud Run Developer
gcloud run services add-iam-policy-binding ${SERVICE_NAME} \
  --region=${REGION} \
  --project=${NEW_PROJECT_ID} \
  --member="serviceAccount:${CI_SERVICE_ACCOUNT}@${NEW_PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/run.developer"

# 1.4.3. Service Account User (to act as the runtime SA)
# Note: This assumes the default compute service account is used by Cloud Run.
PROJECT_NUMBER=$(gcloud projects describe ${NEW_PROJECT_ID} --format="value(projectNumber)")
gcloud iam service-accounts add-iam-policy-binding "${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --project=${NEW_PROJECT_ID} \
  --member="serviceAccount:${CI_SERVICE_ACCOUNT}@${NEW_PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# 1.5. Create Workload Identity Pool
gcloud iam workload-identity-pools create "github-pool" \
  --project=${NEW_PROJECT_ID} \
  --location="global" \
  --display-name="GitHub Actions Pool"

# 1.6. Create Workload Identity Provider with condition for your repo
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project=${NEW_PROJECT_ID} \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Actions Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository == '${GITHUB_REPO}'" \
  --issuer-uri="https://token.actions.githubusercontent.com"

# 1.7. Allow GitHub to impersonate the CI/CD service account
gcloud iam service-accounts add-iam-policy-binding "${CI_SERVICE_ACCOUNT}@${NEW_PROJECT_ID}.iam.gserviceaccount.com" \
  --project=${NEW_PROJECT_ID} \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/${GITHUB_REPO}"

# 1.8. Grant the CI/CD service account the ability to generate tokens (for itself)
gcloud iam service-accounts add-iam-policy-binding "${CI_SERVICE_ACCOUNT}@${NEW_PROJECT_ID}.iam.gserviceaccount.com" \
  --project=${NEW_PROJECT_ID} \
  --role="roles/iam.serviceAccountTokenCreator" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/${GITHUB_REPO}"


# ==============================================================================
# SECTION 2: DEPLOYMENT INFRASTRUCTURE (Cloud Run + LB + IAP)
# ==============================================================================
echo "--- Section 2: Setting up Deployment Infrastructure ---"

# 2.1. Enable required APIs for deployment
gcloud services enable run.googleapis.com artifactregistry.googleapis.com compute.googleapis.com iap.googleapis.com --project=${NEW_PROJECT_ID}

# 2.2. Create Artifact Registry repository
gcloud artifacts repositories create ${AR_REPO_NAME} \
  --repository-format=docker \
  --location=${REGION} \
  --project=${NEW_PROJECT_ID}

# 2.3. Deploy the initial Cloud Run service (can be done via CI/CD)
# NOTE: The GitHub Actions workflow handles this. This is a manual example.
# gcloud run deploy ${SERVICE_NAME} --image=... --project=${NEW_PROJECT_ID} --region=${REGION}

# 2.4. Create Serverless NEG for the Cloud Run service
gcloud compute network-endpoint-groups create ${NEG_NAME} \
  --project=${NEW_PROJECT_ID} \
  --region=${REGION} \
  --network-endpoint-type=serverless \
  --cloud-run-service=${SERVICE_NAME}

# 2.5. Create Global External Load Balancer components
# 2.5.1. Create Backend Service
gcloud compute backend-services create ${BACKEND_SERVICE_NAME} \
  --project=${NEW_PROJECT_ID} \
  --global

# 2.5.2. Add NEG to Backend Service
gcloud compute backend-services add-backend ${BACKEND_SERVICE_NAME} \
  --project=${NEW_PROJECT_ID} \
  --global \
  --network-endpoint-group=${NEG_NAME} \
  --network-endpoint-group-region=${REGION}

# 2.5.3. Create URL Map
gcloud compute url-maps create ${URL_MAP_NAME} \
  --project=${NEW_PROJECT_ID} \
  --default-service=${BACKEND_SERVICE_NAME}

# 2.5.4. Create Google-managed SSL Certificate
gcloud compute ssl-certificates create ${SSL_CERT_NAME} \
  --project=${NEW_PROJECT_ID} \
  --domains=${DOMAIN_NAME} \
  --global

# 2.5.5. Create Target HTTPS Proxy
gcloud compute target-https-proxies create ${HTTPS_PROXY_NAME} \
  --project=${NEW_PROJECT_ID} \
  --url-map=${URL_MAP_NAME} \
  --ssl-certificates=${SSL_CERT_NAME}

# 2.5.6. Create Global Static IP Address
gcloud compute addresses create ${IP_NAME} \
  --project=${NEW_PROJECT_ID} \
  --global

# 2.5.7. Create Forwarding Rule
gcloud compute forwarding-rules create ${FW_RULE_NAME} \
  --project=${NEW_PROJECT_ID} \
  --address=${IP_NAME} \
  --target-https-proxy=${HTTPS_PROXY_NAME} \
  --ports=443 \
  --global

# 2.6. Enable IAP on the Backend Service
gcloud compute backend-services update ${BACKEND_SERVICE_NAME} \
  --project=${NEW_PROJECT_ID} \
  --iap=enabled \
  --global

# 2.7. Grant your user access through IAP (via UI is often easier)
# This command requires setting up an OAuth Consent Screen first.
# Go to Security -> Identity-Aware Proxy in the UI, select the backend service,
# and add the principal with the "IAP-secured Web App User" role.
echo "ACTION REQUIRED: Manually grant ${ADMIN_USER_EMAIL} the 'IAP-secured Web App User' role in the IAP console."

# 2.8. Grant the IAP service agent permission to invoke the Cloud Run service
gcloud run services add-iam-policy-binding ${SERVICE_NAME} \
  --project=${NEW_PROJECT_ID} \
  --region=${REGION} \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com" \
  --role="roles/run.invoker"

# 2.9. Lock down the Cloud Run service to only accept traffic from the LB
gcloud run services update ${SERVICE_NAME} \
  --project=${NEW_PROJECT_ID} \
  --region=${REGION} \
  --ingress=internal-and-cloud-load-balancing

echo "--- Setup Complete ---"
echo "ACTION REQUIRED: Create a DNS A-record for ${DOMAIN_NAME} pointing to the IP of ${IP_NAME}."
