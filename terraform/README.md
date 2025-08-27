
# Terraform Configuration for The Fraud Digest Weekly

This directory contains the Terraform configuration for deploying the necessary infrastructure for The Fraud Digest Weekly application.

## Prerequisites

- Terraform v1.0.0 or later
- Google Cloud SDK

## Usage

1.  Initialize Terraform:

    ```bash
    terraform init
    ```

2.  Create a `terraform.tfvars` file and populate it with your project-specific values:

    ```hcl
    project_id = "your-gcp-project-id"
    region     = "your-gcp-region"
    ```

3.  Apply the Terraform configuration:

    ```bash
    terraform apply
    ```
