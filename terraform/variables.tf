// terraform/variables.tf

variable "gcp_project_id" {
  type        = string
  description = "The Google Cloud project ID where resources will be deployed."
}

variable "gcp_region" {
  type        = string
  description = "The Google Cloud region for deploying resources."
  default     = "europe-west1"
}

variable "frontend_service_name" {
  type        = string
  description = "The name of the frontend Cloud Run service."
  default     = "fraud-digest-frontend"
}

variable "repository_id" {
  type        = string
  description = "The ID of the Artifact Registry repository for Docker images."
  default     = "fraud-digest-repo"
}

variable "pubsub_topic_id" {
  type        = string
  description = "The ID of the Pub/Sub topic for job submissions."
  default     = "fraud-digest-jobs"
}

variable "gcp_service_list" {
  description = "The list of GCP services to enable for the frontend"
  type        = list(string)
  default = [
    "iam.googleapis.com",
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "iamcredentials.googleapis.com",
    "pubsub.googleapis.com"
  ]
}

variable "gcp_support_email" {
  type        = string
  description = "The email address to display on the OAuth consent screen."
  default     = "maya.fudim@axionym.com"
}

