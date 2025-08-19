***

# Руководство по развертыванию и настройке CI/CD

Этот документ описывает полный процесс развертывания защищенного веб-приложения в Google Cloud Run с использованием Балансировщика Нагрузки, Identity-Aware Proxy (IAP) для аутентификации, а также настройку полностью автоматизированного CI/CD конвейера с помощью GitHub Actions и Workload Identity Federation.
Здесь вы найдёте все шаги (команды и действия в GUI), объяснение причин для каждого действия, а также инструкции по поиску необходимых ID.

## Предварительные требования

1.  **Аккаунт Google Cloud:** С привязанным платежным аккаунтом.
2.  **Права доступа:** Вы должны обладать правами `Owner` или `Admin` на уровне Организации Google Cloud для управления политиками.
3.  **Доменное имя:** У вас должен быть доступ к настройкам DNS для домена, который вы будете использовать.
4.  **Установленные инструменты:** `gcloud` CLI, `docker`.
5.  **Репозиторий GitHub:** Код приложения должен находиться в репозитории GitHub.

---

## Часть I: Конфигурация и поиск ID

Перед началом скопируйте этот блок в текстовый редактор и заполните все переменные. Они будут использоваться во всех последующих командах.

### Как найти необходимые ID

*   **`ORGANIZATION_ID`:** Выполните `gcloud organizations list`.
*   **`CUSTOMER_ID`:** Выполните `gcloud organizations list` и найдите значение в столбце `DIRECTORY_CUSTOMER_ID`.
*   **`BILLING_ACCOUNT_ID`:** Выполните `gcloud beta billing accounts list`.
*   **`PROJECT_ID`:** Будет сгенерирован при создании проекта.
*   **`PROJECT_NUMBER`:** Выполните `gcloud projects describe <YOUR_PROJECT_ID> --format="value(projectNumber)"` после создания проекта.

### Переменные для настройки

```bash
# --- Конфигурация Проекта и Организации ---
export ORGANIZATION_ID="<YOUR_ORGANIZATION_ID>" # Пример: 303337513280
export CUSTOMER_ID="<YOUR_CUSTOMER_ID>"       # Пример: C00ueh1pc
export BILLING_ACCOUNT_ID="<YOUR_BILLING_ACCOUNT_ID>" # Пример: 015A12-204E88-9F704C
export NEW_PROJECT_ID="<CHOOSE_A_UNIQUE_PROJECT_ID>" # Пример: fraud-digest-app-v2-469310
export REGION="europe-west1"

# --- Конфигурация Приложения и CI/CD ---
export GITHUB_REPO="<YOUR_GITHUB_USERNAME_OR_ORG>/<YOUR_REPO_NAME>" # Пример: mayafudimaxionym/The-Fraud-Digest-Weekly-app
export SERVICE_NAME="fraud-digest-weekly-app"
export DOMAIN_NAME="<YOUR_SUBDOMAIN.YOUR_DOMAIN.COM>" # Пример: frapp.axionym.com

# --- Имена Ресурсов (можно оставить по умолчанию) ---
export AR_REPO_NAME="fraud-digest-repo"
export IMAGE_NAME="the-fraud-digest-weekly-app"
export CI_SERVICE_ACCOUNT="github-actions-deployer"
export NEG_NAME="fraud-digest-neg"
export BACKEND_SERVICE_NAME="fraud-digest-backend"
export URL_MAP_NAME="fraud-digest-url-map"
export SSL_CERT_NAME="fraud-digest-ssl-cert"
export HTTPS_PROXY_NAME="fraud-digest-https-proxy"
export IP_NAME="fraud-digest-ip"
export FW_RULE_NAME="fraud-digest-forwarding-rule"

# --- Конфигурация Пользователя ---
export ADMIN_USER_EMAIL="<YOUR_GOOGLE_ACCOUNT_EMAIL>" # Пример: maya.fudim@axionym.com
```

---

## Часть II: Создание и настройка проекта

**Цель:** Создать изолированное окружение (проект) для нашего приложения.

1.  **Создание проекта**
    *   **Действие:** Выполните команду:
        ```bash
        gcloud projects create ${NEW_PROJECT_ID} --name="<A_DESCRIPTIVE_NAME>"
        ```
    *   **Причина:** Создает контейнер для всех ресурсов, биллинга и разрешений.

2.  **Привязка платежного аккаунта**
    *   **Действие:** Выполните команду:
        ```bash
        gcloud beta billing projects link ${NEW_PROJECT_ID} --billing-account=${BILLING_ACCOUNT_ID}
        ```
    *   **Причина:** Позволяет использовать платные сервисы Google Cloud, такие как Cloud Run и Load Balancer.

3.  **Установка проекта как активного**
    *   **Действие:** Выполните команду:
        ```bash
        gcloud config set project ${NEW_PROJECT_ID}
        ```
    *   **Причина:** Устанавливает контекст по умолчанию для всех последующих `gcloud` команд.

4.  **Включение необходимых API**
    *   **Действие:** Выполните команду:
        ```bash
        gcloud services enable run.googleapis.com artifactregistry.googleapis.com compute.googleapis.com iap.googleapis.com iamcredentials.googleapis.com
        ```
    *   **Причина:** Активирует сервисы Cloud Run, Artifact Registry, Compute Engine (для Балансировщика), IAP и IAM Credentials API для их совместной работы.

---

## Часть III: Настройка CI/CD (Workload Identity Federation)

**Цель:** Настроить безопасный, безключевой доступ для GitHub Actions к вашему проекту Google Cloud.

1.  **Создание сервисного аккаунта для CI/CD**
    *   **Действие:** Выполните команду:
        ```bash
        gcloud iam service-accounts create ${CI_SERVICE_ACCOUNT} --project=${NEW_PROJECT_ID} --display-name="GitHub Actions Deployer"
        ```    *   **Причина:** Создает специального "робота" (сервисный аккаунт), от имени которого GitHub будет выполнять развертывание.

2.  **Создание Пула Удостоверений (Workload Identity Pool)**
    *   **Действие:** Выполните команду:
        ```bash
        gcloud iam workload-identity-pools create "github-pool" --project=${NEW_PROJECT_ID} --location="global" --display-name="GitHub Actions Pool"
        ```
    *   **Причина:** Создает "клуб доверия", который будет принимать удостоверения от внешних систем (в нашем случае, GitHub).

3.  **Создание Провайдера Удостоверений (Workload Identity Provider)**
    *   **Действие:** Выполните команду:
        ```bash
        gcloud iam workload-identity-pools providers create-oidc "github-provider" --project=${NEW_PROJECT_ID} --location="global" --workload-identity-pool="github-pool" --display-name="GitHub Actions Provider" --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" --attribute-condition="assertion.repository == '${GITHUB_REPO}'" --issuer-uri="https://token.actions.githubusercontent.com"
        ```
    *   **Причина:** Регистрирует GitHub как доверенного провайдера и устанавливает **критически важное условие**: доверять токенам **только** от вашего конкретного репозитория.

4.  **Связывание GitHub с сервисным аккаунтом**
    *   **Действие:** Выполните команду (сначала получите `PROJECT_NUMBER`):
        ```bash
        PROJECT_NUMBER=$(gcloud projects describe ${NEW_PROJECT_ID} --format="value(projectNumber)")
        gcloud iam service-accounts add-iam-policy-binding "${CI_SERVICE_ACCOUNT}@${NEW_PROJECT_ID}.iam.gserviceaccount.com" --project=${NEW_PROJECT_ID} --role="roles/iam.workloadIdentityUser" --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/${GITHUB_REPO}"
        ```
    *   **Причина:** Позволяет аутентифицированным запросам из вашего репозитория на GitHub "выдавать себя" за созданный нами сервисный аккаунт.

5.  **Предоставление прав сервисному аккаунту CI/CD**
    *   **Действие:** Выполните следующие команды:
        ```bash
        # Право загружать образы
        gcloud artifacts repositories add-iam-policy-binding ${AR_REPO_NAME} --location=${REGION} --project=${NEW_PROJECT_ID} --member="serviceAccount:${CI_SERVICE_ACCOUNT}@${NEW_PROJECT_ID}.iam.gserviceaccount.com" --role="roles/artifactregistry.writer"

        # Право развертывать в Cloud Run
        gcloud run services add-iam-policy-binding ${SERVICE_NAME} --region=${REGION} --project=${NEW_PROJECT_ID} --member="serviceAccount:${CI_SERVICE_ACCOUNT}@${NEW_PROJECT_ID}.iam.gserviceaccount.com" --role="roles/run.developer"

        # Право действовать от имени рантайм-аккаунта Cloud Run
        gcloud iam service-accounts add-iam-policy-binding "${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" --project=${NEW_PROJECT_ID} --member="serviceAccount:${CI_SERVICE_ACCOUNT}@${NEW_PROJECT_ID}.iam.gserviceaccount.com" --role="roles/iam.serviceAccountUser"

        # Право создавать токены доступа (необходимо для gcloud auth)
        gcloud iam service-accounts add-iam-policy-binding "${CI_SERVICE_ACCOUNT}@${NEW_PROJECT_ID}.iam.gserviceaccount.com" --project=${NEW_PROJECT_ID} --role="roles/iam.serviceAccountTokenCreator" --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/${GITHUB_REPO}"
        ```
    *   **Причина:** Предоставляет "роботу" минимально необходимые права для выполнения его задач: загрузки образов и развертывания сервиса.

---

## Часть IV: Развертывание инфраструктуры (LB + IAP)

**Цель:** Создать Балансировщик Нагрузки, который будет служить защищенной точкой входа для нашего приложения.

1.  **Создание репозитория Artifact Registry**
    *   **Действие:** Выполните команду:
        ```bash
        gcloud artifacts repositories create ${AR_REPO_NAME} --repository-format=docker --location=${REGION} --project=${NEW_PROJECT_ID}
        ```
    *   **Причина:** Создает приватное, защищенное хранилище для наших Docker-образов.

2.  **Создание статического IP-адреса**
    *   **Действие:** Выполните команду и **сохраните IP-адрес**:
        ```bash
        gcloud compute addresses create ${IP_NAME} --project=${NEW_PROJECT_ID} --global
        gcloud compute addresses describe ${IP_NAME} --project=${NEW_PROJECT_ID} --global --format="value(address)"
        ```
    *   **Причина:** Резервирует постоянный публичный IP-адрес для нашего Балансировщика.

3.  **Создание Serverless NEG**
    *   **Действие:** Выполните команду:
        ```bash
        gcloud compute network-endpoint-groups create ${NEG_NAME} --project=${NEW_PROJECT_ID} --region=${REGION} --network-endpoint-type=serverless --cloud-run-service=${SERVICE_NAME}
        ```
    *   **Причина:** Создает "коннектор" между Балансировщиком и нашим сервисом Cloud Run.

4.  **Создание Бэкенд-сервиса**
    *   **Действие:** Выполните команду:
        ```bash
        gcloud compute backend-services create ${BACKEND_SERVICE_NAME} --project=${NEW_PROJECT_ID} --global
        ```
    *   **Причина:** Создает логический компонент, который будет управлять бэкендами (нашим NEG).

5.  **Привязка NEG к Бэкенд-сервису**
    *   **Действие:** Выполните команду:
        ```bash
        gcloud compute backend-services add-backend ${BACKEND_SERVICE_NAME} --project=${NEW_PROJECT_ID} --global --network-endpoint-group=${NEG_NAME} --network-endpoint-group-region=${REGION}
        ```
    *   **Причина:** Сообщает Бэкенд-сервису, куда отправлять трафик.

6.  **Создание Карты URL**
    *   **Действие:** Выполните команду:
        ```bash
        gcloud compute url-maps create ${URL_MAP_NAME} --project=${NEW_PROJECT_ID} --default-service=${BACKEND_SERVICE_NAME}
        ```
    *   **Причина:** Создает правило маршрутизации: "весь трафик (`*`) отправлять на наш бэкенд".

7.  **Создание SSL-сертификата**
    *   **Действие:** Выполните команду:
        ```bash
        gcloud compute ssl-certificates create ${SSL_CERT_NAME} --project=${NEW_PROJECT_ID} --domains=${DOMAIN_NAME} --global
        ```
    *   **Причина:** Создает SSL-сертификат, управляемый Google, для нашего домена, обеспечивая HTTPS.

8.  **Создание Целевого HTTPS-прокси**
    *   **Действие:** Выполните команду:
        ```bash
        gcloud compute target-https-proxies create ${HTTPS_PROXY_NAME} --project=${NEW_PROJECT_ID} --url-map=${URL_MAP_NAME} --ssl-certificates=${SSL_CERT_NAME}
        ```
    *   **Причина:** Связывает наш SSL-сертификат с правилами маршрутизации.

9.  **Создание Правила пересылки**
    *   **Действие:** Выполните команду:
        ```bash
        gcloud compute forwarding-rules create ${FW_RULE_NAME} --project=${NEW_PROJECT_ID} --address=${IP_NAME} --target-https-proxy=${HTTPS_PROXY_NAME} --ports=443 --global
        ```
    *   **Причина:** Связывает наш публичный IP-адрес с HTTPS-прокси, завершая создание Балансировщика.

---

## Часть V: Финальная настройка (GUI и DNS)

**Цель:** Включить IAP и направить наш домен на Балансировщик.

1.  **Настройка Экрана согласия OAuth (GUI)**
    *   **Действие:**
        1.  Перейдите в `APIs & Services` -> `OAuth consent screen`.
        2.  Выберите `Internal` и нажмите `Create`.
        3.  Заполните обязательные поля (App name, User support email, Developer contact) и нажимайте `Save and Continue` до конца.
    *   **Причина:** IAP требует наличия Экрана согласия для отображения страницы входа Google пользователям.

2.  **Включение IAP и предоставление прав (GUI)**
    *   **Действие:**
        1.  Перейдите в `Security` -> `Identity-Aware Proxy`.
        2.  Найдите в списке ресурс `fraud-digest-backend` и **включите** для него IAP с помощью переключателя. Система может попросить вас подтвердить создание OAuth-клиента.
        3.  Выберите этот ресурс (поставьте галочку). Справа откроется панель.
        4.  Нажмите `Add Principal`.
        5.  В поле "New principals" введите ваш email (`${ADMIN_USER_EMAIL}`).
        6.  В поле "Select a role" выберите `Cloud IAP` -> `IAP-secured Web App User`.
        7.  Нажмите `Save`.
    *   **Причина:** Включает "главного охранника" (IAP) и добавляет вас в список тех, кому разрешен вход.

3.  **Настройка сервиса Cloud Run**
    *   **Действие:** Выполните следующие команды:
        ```bash
        # Ограничиваем доступ к сервису только от Балансировщика
        gcloud run services update ${SERVICE_NAME} --project=${NEW_PROJECT_ID} --region=${REGION} --ingress=internal-and-cloud-load-balancing

        # Предоставляем сервисному агенту IAP право вызывать наш сервис
        gcloud run services add-iam-policy-binding ${SERVICE_NAME} --project=${NEW_PROJECT_ID} --region=${REGION} --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com" --role="roles/run.invoker"
        ```
    *   **Причина:** Мы создаем защищенный канал между Балансировщиком и Cloud Run, запрещая любой прямой доступ к сервису.

4.  **Настройка DNS (внешнее действие)**
    *   **Действие:**
        1.  Войдите в панель управления вашего DNS-провайдера.
        2.  Создайте новую **`A`-запись**.
        3.  **Host/Name:** `frapp` (или та часть, которая идет до `.axionym.com`).
        4.  **Value/Points to:** IP-адрес, который вы получили на шаге 4.2.
    *   **Причина:** Направляет ваш субдомен на публичный IP-адрес Балансировщика Нагрузки.

После завершения всех шагов и обновления DNS (может занять до часа), ваше приложение будет доступно по вашему домену и защищено с помощью IAP. Смотри также *setup_guide.sh*, который содержит в себе все эти комманды.
