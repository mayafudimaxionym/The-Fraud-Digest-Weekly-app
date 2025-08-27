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

// Enable all necessary APIs for the project in one go
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "iam.googleapis.com",
    "pubsub.googleapis.com"
  ])
  service                    = each.key
  disable_dependency_violation = true
}

// 1. Create a Pub/Sub topic for the frontend to send jobs to
resource "google_pubsub_topic" "jobs_topic" {
  name       = var.pubsub_topic_id
  depends_on = [google_project_service.apis]
}

// 2. Create a repository in Artifact Registry to store our Docker images
resource "google_artifact_registry_repository" "repo" {
  location      = var.gcp_region
  repository_id = var.repository_id
  description   = "Docker repository for fraud-digest application"
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

// 3. Create a dedicated Service Account for the frontend service for security
resource "google_service_account" "frontend_sa" {
  account_id   = "${var.frontend_service_name}-sa"
  display_name = "Service Account for Fraud Digest Frontend"
}

// 4. Grant the frontend's Service Account the permission to publish messages to our topic
resource "google_pubsub_topic_iam_member" "publisher" {
  topic  = google_pubsub_topic.jobs_topic.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.frontend_sa.email}"
}

// 5. Create the Cloud Run service to run our frontend container
resource "google_cloud_run_v2_service" "frontend_service" {
  name     = var.frontend_service_name
  location = var.gcp_region

  template {
    // Run the service using our dedicated service account
    service_account = google_service_account.frontend_sa.email
    
    containers {
      // The image will be specified during the deployment step in the CI/CD pipeline
      image = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/${google_artifact_registry_repository.repo.repository_id}/${var.frontend_service_name}:latest"
      
      // Pass the Pub/Sub topic ID and Project ID to the application as environment variables
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

  // Allow unauthenticated (public) access to the frontend service
  iam_policy {
    policy_data = data.google_iam_policy.noauth.policy_data
  }

  depends_on = [
    google_project_service.apis,
    google_pubsub_topic_iam_member.publisher
  ]
}

// Policy data to make the Cloud Run service publicly accessible
data "google_iam_policy" "noauth" {
  binding {
    role    = "roles/run.invoker"
    members = ["allUsers"]
  }
}

// Output the URL of the deployed frontend service
output "frontend_service_url" {
  value = google_cloud_run_v2_service.frontend_service.uri
}
