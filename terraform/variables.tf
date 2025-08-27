
variable "project_id" {
  description = "The project ID to host the solution"
  type        = string
}

variable "region" {
  description = "The region to host the solution"
  type        = string
  default     = "us-central1"
}

variable "gcp_service_list" {
  description = "The list of GCP services to enable"
  type        = list(string)
  default = [
    "iam.googleapis.com",
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "iamcredentials.googleapis.com",
    "storage.googleapis.com"
  ]
}
