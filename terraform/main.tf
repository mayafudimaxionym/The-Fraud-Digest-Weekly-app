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

// terraform/main.tf

// ... (все существующие ресурсы для frontend) ...

// === Backend Infrastructure (Cloud Function) ===

// 6. Создаем сервисный аккаунт специально для Backend функции
resource "google_service_account" "backend_sa" {
  project      = var.gcp_project_id
  account_id   = "fraud-digest-backend-sa"
  display_name = "Service Account for Fraud Digest Backend"
}

// 7. Даем сервисному аккаунту Backend права на вызов Vertex AI
resource "google_project_iam_member" "backend_vertex_ai_user" {
  project = var.gcp_project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

// 8. Даем сервисному аккаунту Backend права на чтение секретов
resource "google_project_iam_member" "backend_secret_accessor" {
  project = var.gcp_project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

// 9. Создаем саму Cloud Function 2-го поколения
resource "google_cloudfunctions2_function" "backend_function" {
  project  = var.gcp_project_id
  name     = "fraud-digest-backend"
  location = var.gcp_region

  # Конфигурация сборки: указываем на исходный код
  build_config {
    runtime     = "python311" # Убедитесь, что соответствует вашему коду
    entry_point = "main"      # Имя функции-обработчика в main.py
    source {
      storage_source {
        # Бакет будет автоматически создан gcloud deploy
        # Это поле обязательно, но gcloud его переопределит
        bucket = google_storage_bucket.source_bucket.name
        object = "source.zip" # Имя объекта будет подставлено gcloud
      }
    }
  }

  # Конфигурация запуска: триггеры и сервисный аккаунт
  service_config {
    max_instance_count = 3
    min_instance_count = 0
    available_memory   = "512Mi"
    timeout_seconds    = 300
    service_account_email = google_service_account.backend_sa.email
    
    # Триггер, который запускает функцию
    event_trigger {
      trigger_region = var.gcp_region
      event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
      pubsub_topic   = google_pubsub_topic.jobs_topic.id
      retry_policy   = "RETRY_POLICY_RETRY" # Автоматически повторять при сбое
    }
  }

  depends_on = [
    google_project_iam_member.backend_vertex_ai_user,
    google_project_iam_member.backend_secret_accessor
  ]
}

// 10. Создаем бакет для исходного кода Cloud Functions (требуется Terraform)
resource "google_storage_bucket" "source_bucket" {
  project      = var.gcp_project_id
  name         = "${var.gcp_project_id}-cf-source" # Имя должно быть уникальным
  location     = var.gcp_region
  uniform_bucket_level_access = true
}

// 11. Разрешаем Pub/Sub создавать токены для вызова нашей (приватной) Cloud Function
resource "google_project_iam_member" "pubsub_invoker" {
  project = var.gcp_project_id
  role    = "roles/run.invoker"
  # Специальный сервисный аккаунт, принадлежащий Pub/Sub
  member  = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

// Data source для получения номера проекта (нужен для pubsub_invoker)
data "google_project" "project" {
  project_id = var.gcp_project_id
}


// terraform/variables.tf
