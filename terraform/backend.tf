# terraform/backend.tf

terraform {
  backend "gcs" {
    bucket  = "tf-state-fraud-digest-app-v2-469310"
    prefix  = "terraform/state"
  }
}