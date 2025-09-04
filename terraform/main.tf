// terraform/main.tf

terraform {
  required_providers {
    google = { source = "hashicorp/google", version = ">= 4.50.0" }
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
  for_each = toset(["iap.googleapis.com", "eventarc.googleapis.com", "firestore.googleapis.com"])
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
resource "google_firestore_database" "database" {
  project     = var.gcp_project_id
  name        = "(default)"
  location_id = var.gcp_region
  type        = "FIRESTORE_NATIVE"
  depends_on  = [google_project_service.extra_apis]
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
      env {
        name  = "GCP_PROJECT_ID"
        value = var.gcp_project_id
      }
      env {
        name  = "PUBSUB_TOPIC_ID"
        value = var.pubsub_topic_id
      }
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
// === BACKEND INFRASTRUCTURE (Cloud Run + Pub/Sub Push) ===
// ===================================================
resource "google_cloud_run_v2_service" "backend_service" {
  project             = var.gcp_project_id
  name                = "fraud-analysis-processor-v2"
  location            = var.gcp_region
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  template {
    service_account = var.gcp_sa_email
    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"
      env {
        name  = "GCP_PROJECT"
        value = var.gcp_project_id
      }
    }
  }
  lifecycle { ignore_changes = all }
}
// --- Pub/Sub Push Subscription ---
resource "google_service_account" "pubsub_push_sa" {
  project      = var.gcp_project_id
  account_id   = "pubsub-push-invoker-sa"
  display_name = "Pub/Sub Push Invoker SA"
}
resource "google_cloud_run_v2_service_iam_member" "pubsub_invoker" {
  project  = google_cloud_run_v2_service.backend_service.project
  location = google_cloud_run_v2_service.backend_service.location
  name     = google_cloud_run_v2_service.backend_service.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_push_sa.email}"
}
resource "google_service_account_iam_member" "pubsub_impersonator" {
  service_account_id = google_service_account.pubsub_push_sa.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}
resource "google_pubsub_subscription" "backend_push_subscription" {
  project              = var.gcp_project_id
  name                 = "backend-push-subscription"
  topic                = google_pubsub_topic.jobs_topic.name
  ack_deadline_seconds = 60
  push_config {
    push_endpoint = google_cloud_run_v2_service.backend_service.uri
    oidc_token {
      service_account_email = google_service_account.pubsub_push_sa.email
    }
  }
  depends_on = [google_cloud_run_v2_service_iam_member.pubsub_invoker]
}
data "google_project" "project" {
  project_id = var.gcp_project_id
}
output "frontend_service_url" {
  value = google_cloud_run_v2_service.frontend_service.uri
}
