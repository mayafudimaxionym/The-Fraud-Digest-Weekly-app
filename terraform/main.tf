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

resource "google_project_service" "apis" {
  for_each           = toset(var.gcp_service_list)
  project            = var.gcp_project_id
  service            = each.key
  disable_on_destroy = false
}
resource "google_project_service" "iap_api" {
  project            = var.gcp_project_id
  service            = "iap.googleapis.com"
  disable_on_destroy = false
}

// === IAP (Identity-Aware Proxy) Configuration ===
resource "google_iap_client" "project_client" {
  display_name = "Fraud Digest IAP Client"
  brand        = "projects/963241002796/brands/963241002796"
}

// === Application Infrastructure ===
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
    scaling {
      max_instance_count = 4
    }
    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"
      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
      }
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

  lifecycle {
    ignore_changes = all
  }

  depends_on = [google_project_service.apis, google_pubsub_topic_iam_member.publisher]
}

// Grant YOUR user the right to invoke the service (required for IAP).
resource "google_cloud_run_v2_service_iam_member" "iap_invoker" {
  project  = google_cloud_run_v2_service.frontend_service.project
  location = google_cloud_run_v2_service.frontend_service.location
  name     = google_cloud_run_v2_service.frontend_service.name
  role     = "roles/run.invoker"
  member   = "user:${var.gcp_support_email}"
}

output "frontend_service_url" {
  value = google_cloud_run_v2_service.frontend_service.uri
}


// terraform/variables.tf
