# --- Cleanup commands for the OLD project ---

# 1. Set context to the old project to be safe
gcloud config set project fraud-digest-project

# 2. Delete the Cloud Run service
gcloud run services delete fraud-digest-weekly-app \
  --project=fraud-digest-project \
  --region=europe-west1 \
  --quiet

# 3. Delete the Artifact Registry repository
# This will also delete all images inside it.
gcloud artifacts repositories delete fraud-digest-repo \
  --project=fraud-digest-project \
  --location=europe-west1 \
  --quiet
  