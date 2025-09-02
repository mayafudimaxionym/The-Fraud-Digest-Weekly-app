// terraform/main.tf

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 4.50.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

// === APIs ===
resource "google_project_service" "apis" {
  for_each           = toset(var.gcp_service_list)
  project            = var.gcp_project_id
  service            = each.key
  disable_on_destroy = false
}
resource "google_project_service" "extra_apis" {
  for_each = toset([
    "iap.googleapis.com",
    "eventarc.googleapis.com" # Add Eventarc API
  ])
  project            = var.gcp_project_id
  service            = each.key
  disable_on_destroy = false
}

// === Shared Infrastructure ===
resource "google_pubsub_topic" "jobs_topic" {
  project    = var.gcp_project_id
  name       = var.pubsub_topic_id
  labels     = {}
  depends_on = [google_project_service.apis]
}
resource "google_artifact_registry_repository" "repo" {
  project       = var.gcp_project_id
  location      = var.gcp_region
  repository_id = var.repository_id
  description   = "Docker repository for fraud-digest application"
  format        = "DOCKER"
  labels        = {}
  depends_on    = [google_project_service.apis]
}

// =================================================
// === FRONTEND INFRASTRUCTURE (Cloud Run + IAP) ===
// =================================================
resource "google_iap_client" "project_client" {
  display_name = "Fraud Digest IAP Client"
  brand        = "projects/963241002796/brands/963241002796"
}
resource "google_service_account" "frontend_sa" {
  project      = var.gcp_project_id
  account_id   = "${var.frontend_service_name}-sa"
  display_name = "Service Account for Fraud Digest Frontend"
  description  = ""
}
resource "google_pubsub_topic_iam_member" "publisher" {
  project = var.gcp_project_id
  topic   = google_pubsub_topic.jobs_topic.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.frontend_sa.email}"
}
resource "google_cloud_run_v2_service" "frontend_service" {
  project             = var.gcp_project_id
  name                = var.frontend_service_name
  location            = var.gcp_region
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"
  client              = google_iap_client.project_client.client_id
  template {
    service_account = google_service_account.frontend_sa.email
    scaling { max_instance_count = 4 }
    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"
      resources { limits = { cpu = "1000m", memory = "512Mi" } }
      env { name = "GCP_PROJECT_ID", value = var.gcp_project_id }
      env { name = "PUBSUB_TOPIC_ID", value = var.pubsub_topic_id }
    }
  }
  lifecycle { ignore_changes = all }
  depends_on = [google_project_service.apis, google_pubsub_topic_iam_member.publisher]
}
resource "google_cloud_run_v2_service_iam_member" "iap_invoker" {
  project  = google_cloud_run_v2_service.frontend_service.project
  location = google_cloud_run_v2_service.frontend_service.location
  name     = google_cloud_run_v2_service.frontend_service.name
  role     = "roles/run.invoker"
  member   = "user:${var.gcp_support_email}"
}

// ===================================================
// === BACKEND INFRASTRUCTURE (Cloud Run + Eventarc) ===
// ===================================================
resource "google_service_account" "backend_sa" {
  project      = var.gcp_project_id
  account_id   = "fraud-digest-backend-sa"
  display_name = "Service Account for Fraud Digest Backend"
  description  = ""
}
resource "google_project_iam_member" "backend_roles" {
  for_each = toset([
    "roles/aiplatform.user",
    "roles/secretmanager.secretAccessor"
  ])
  project = var.gcp_project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}
resource "google_cloud_run_v2_service" "backend_service" {
  project             = var.gcp_project_id
  name                = "fraud-analysis-processor-v2" # From your deploy.yaml
  location            = var.gcp_region
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY" # Internal service
  template {
    service_account = google_service_account.backend_sa.email
    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello" # Placeholder
      env { name = "GCP_PROJECT", value = var.gcp_project_id }
    }
  }
  lifecycle { ignore_changes = all }
  depends_on = [google_project_iam_member.backend_roles]
}

// --- Eventarc Trigger ---
resource "google_service_account" "eventarc_sa" {
  project      = var.gcp_project_id
  account_id   = "eventarc-trigger-sa"
  display_name = "Eventarc Trigger Service Account"
}
resource "google_project_iam_member" "eventarc_roles" {
  for_each = toset([
    "roles/eventarc.eventReceiver",
    "roles/run.invoker" # Allows Eventarc to invoke the Cloud Run service
  ])
  project = var.gcp_project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.eventarc_sa.email}"
}
resource "google_project_iam_member" "pubsub_token_creator" {
  project = var.gcp_project_id
  role    = "roles/iam.serviceAccountTokenCreator"
  member  = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}
resource "google_eventarc_trigger" "backend_trigger" {
  project         = var.gcp_project_id
  name            = "fraud-analysis-processor-v2-trigger" # From your deploy.yaml
  location        = var.gcp_region
  service_account = google_service_account.eventarc_sa.email

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.pubsub.topic.v1.messagePublished"
  }

  destination {
    cloud_run_service {
      service = google_cloud_run_v2_service.backend_service.name
      region  = google_cloud_run_v2_service.backend_service.location
    }
  }

  transport {
    pubsub {
      topic = google_pubsub_topic.jobs_topic.id
    }
  }
  depends_on = [
    google_project_iam_member.eventarc_roles,
    google_project_iam_member.pubsub_token_creator
  ]
}

// Data source to get the project number
data "google_project" "project" {
  project_id = var.gcp_project_id
}

// === Outputs ===
output "frontend_service_url" {
  value = google_cloud_run_v2_service.frontend_service.uri
}