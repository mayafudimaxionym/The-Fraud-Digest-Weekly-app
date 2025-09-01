// terraform/outputs.tf

output "gcp_project_id" {
  description = "The project ID where resources are deployed."
  value       = var.gcp_project_id
}

output "gcp_region" {
  description = "The region where resources are deployed."
  value       = var.gcp_region
}
