***

# Руководство по развертыванию и CI/CD: The Fraud Digest Weekly

Этот документ описывает полный, проверенный на практике процесс развертывания веб-приложения и асинхронного бэкенда в Google Cloud. Архитектура включает защищенный доступ через IAP, асинхронную обработку задач через Pub/Sub и Cloud Functions, а также полностью автоматизированный CI/CD конвейер с помощью GitHub Actions.

Здесь вы найдёте все шаги (команды и действия в GUI), объяснение причин для каждого действия, а также инструкции по поиску необходимых ID.

## 0. Финальная структура проекта

```
The-Fraud-Digest-Weekly-app/
│
├── .github/
│   └── workflows/
│       └── deploy.yaml        # CI/CD пайплайн для GitHub Actions
│
├── backend/
│   ├── main.py              # Код Cloud Function (анализ и отправка email)
│   ├── requirements.txt     # Зависимости для Cloud Function
│   └── Procfile             # Указывает, как запускать Cloud Function в Cloud Run
│
├── frontend/
│   ├── .streamlit/
│   │   └── config.toml
│   ├── src/                 # Модули Streamlit-приложения
│   │   └── ...
│   ├── app.py               # Код Streamlit-приложения (отправка задач)
│   └── requirements.txt     # Зависимости для Streamlit
│
├── Dockerfile                 # Dockerfile для сборки frontend-приложения
└── .dockerignore              # Исключения для Docker-контекста
```

## 1. Стратегия

### 1.1. План: "Crawl, Walk, Run"
Мы следовали поэтапной стратегии для построения нашего приложения:
1.  **Crawl (Ползти):** Создание базового, работающего приложения в Docker-контейнере.
2.  **Walk (Идти):** Развертывание приложения в облаке, защита его с помощью IAP и разделение на frontend и асинхронный backend.
3.  **Run (Бежать):** Улучшение качества AI-анализа с помощью Vertex AI и полная автоматизация CI/CD.

### 1.2. Текущий статус: Фаза "Run" завершена
На данный момент мы успешно завершили все запланированные фазы. Система полностью функциональна.

### 1.3. Следующие шаги
Следующим логическим шагом будет **соединение Frontend и Backend**:
1.  Изменить код `frontend/app.py`, чтобы при нажатии кнопки "Analyze" он отправлял сообщение в Pub/Sub.
2.  Настроить CI/CD для автоматического развертывания frontend-приложения.

---

## 2. Конфигурация в GUI

В процессе настройки были выполнены следующие ключевые действия в веб-интерфейсах.

### 2.1. Google Cloud Console
1.  **OAuth Consent Screen (Экран согласия OAuth):**
    *   **Путь:** `APIs & Services` -> `OAuth consent screen`.
    *   **Действие:** Был создан экран согласия с типом **`Internal`**.
    *   **Причина:** Необходимо для работы IAP, чтобы он мог отображать страницу входа Google пользователям.

2.  **Identity-Aware Proxy (IAP) Permissions:**
    *   **Путь:** `Security` -> `Identity-Aware Proxy`.
    *   **Действие:**
        1.  В списке ресурсов был найден бэкенд-сервис Балансировщика (`fraud-digest-backend`).
        2.  Для него был включен IAP.
        3.  В боковой панели разрешений был добавлен пользователь `maya.fudim@axionym.com` с ролью **`IAP-secured Web App User`**.
    *   **Причина:** Основной механизм защиты frontend-приложения.

### 2.2. DNS-провайдер (например, Porkbun)
*   **Путь:** Панель управления DNS для домена `axionym.com`.
*   **Действие:** Была создана **`A`-запись**.
    *   **Host/Name:** `frapp`
    *   **Value/Points to:** `34.8.149.15` (IP-адрес, полученный на шаге 3.3.7).
*   **Причина:** Связывание доменного имени `https://frapp.axionym.com` с инфраструктурой в Google Cloud.

### 2.3. Resend (Сервис отправки Email)
*   **Путь:** Панель управления Resend.
*   **Действие:**
    1.  Был зарегистрирован аккаунт.
    2.  Был добавлен и подтвержден домен `axionym.com`.
    3.  Был создан **API-ключ** с правами `Sending access`.
*   **Причина:** Получение API-ключа для надежной отправки email из Cloud Function.

---

## 3. "Поваренная книга" CLI команд

Это последовательный список **успешно выполненных** команд для создания всей инфраструктуры и CI/CD с нуля.

### 3.1. Переменные и их получение

Перед началом работы определите следующие переменные.

*   **`NEW_PROJECT_ID`**: Уникальный ID для вашего нового проекта (например, `fraud-digest-app-v2-469310`).
*   **`NEW_PROJECT_NAME`**: Человекочитаемое имя проекта (например, `"My New App"`).
*   **`BILLING_ACCOUNT_ID`**:
    *   **Как найти:** `gcloud beta billing accounts list`
    *   **Пример:** `015A12-204E88-9F704C`
*   **`REGION`**: Основной регион для развертывания.
    *   **Пример:** `europe-west1`
*   **`GITHUB_REPO`**: Ваш репозиторий в формате `владелец/имя`.
    *   **Пример:** `mayafudimaxionym/The-Fraud-Digest-Weekly-app`
*   **`DOMAIN_NAME`**: Полное доменное имя для frontend.
    *   **Пример:** `frapp.axionym.com`
*   **`ADMIN_USER_EMAIL`**: Ваш email для предоставления доступа через IAP.
    *   **Пример:** `maya.fudim@axionym.com`
*   **`RESEND_API_KEY`**:
    *   **Как найти:** Создается в панели управления Resend в разделе `API Keys`.
    *   **Пример:** `re_...`

### 3.2. Локальная разработка и работа с Git

```powershell
# Клонирование репозитория (выполняется один раз)
git clone <URL_ВАШЕГО_РЕПОЗИТОРИЯ>

# Активация виртуального окружения
.\.venv\Scripts\Activate.ps1

# Установка зависимостей для локальной разработки
pip install -r frontend/requirements.txt
pip install -r backend/requirements.txt

# --- Цикл разработки ---
# 1. Внесите изменения в код

# 2. Добавьте измененные файлы для коммита
git add . # Добавить все измененные файлы
# или
git add path/to/your/file.py # Добавить конкретный файл

# 3. Зафиксируйте изменения с осмысленным сообщением
git commit -m "feat(backend): Add new feature to the backend"

# 4. Отправьте изменения на GitHub. Эта команда запускает CI/CD пайплайн.
git push origin main
```

### 3.3. Настройка проекта Google Cloud
```powershell
# Создание нового проекта
gcloud projects create fraud-digest-app-v2-469310 --name="Fraud Digest App V2"

# Привязка платежного аккаунта
gcloud beta billing projects link fraud-digest-app-v2-469310 --billing-account=015A12-204E88-9F704C

# Установка проекта как активного
gcloud config set project fraud-digest-app-v2-469310
gcloud auth application-default set-quota-project fraud-digest-app-v2-469310

# Включение всех необходимых API
gcloud services enable run.googleapis.com artifactregistry.googleapis.com compute.googleapis.com iap.googleapis.com iamcredentials.googleapis.com secretmanager.googleapis.com pubsub.googleapis.com cloudfunctions.googleapis.com cloudbuild.googleapis.com eventarc.googleapis.com aiplatform.googleapis.com
```

### 3.4. Развертывание Frontend (Cloud Run + LB + IAP)
```powershell
# 1. Создание репозитория для Docker-образов
gcloud artifacts repositories create fraud-digest-repo --repository-format=docker --location=europe-west1

# 2. Сборка Docker-образа frontend
docker build -t europe-west1-docker.pkg.dev/fraud-digest-app-v2-469310/fraud-digest-repo/the-fraud-digest-weekly-app:latest -f Dockerfile .

# 3. Отправка образа в Artifact Registry
docker push europe-west1-docker.pkg.dev/fraud-digest-app-v2-469310/fraud-digest-repo/the-fraud-digest-weekly-app:latest

# 4. Первичное развертывание сервиса Cloud Run
gcloud run deploy fraud-digest-weekly-app --image=europe-west1-docker.pkg.dev/fraud-digest-app-v2-469310/fraud-digest-repo/the-fraud-digest-weekly-app:latest --project=fraud-digest-app-v2-469310 --region=europe-west1

# 5. Создание Serverless NEG
gcloud compute network-endpoint-groups create fraud-digest-neg --region=europe-west1 --network-endpoint-type=serverless --cloud-run-service=fraud-digest-weekly-app

# 6. Создание компонентов Балансировщика Нагрузки
gcloud compute backend-services create fraud-digest-backend --global
gcloud compute backend-services add-backend fraud-digest-backend --global --network-endpoint-group=fraud-digest-neg --network-endpoint-group-region=europe-west1
gcloud compute url-maps create fraud-digest-url-map --default-service=fraud-digest-backend
gcloud compute ssl-certificates create fraud-digest-ssl-cert --domains=frapp.axionym.com --global
gcloud compute target-https-proxies create fraud-digest-https-proxy --url-map=fraud-digest-url-map --ssl-certificates=fraud-digest-ssl-cert
gcloud compute addresses create fraud-digest-ip --global
gcloud compute forwarding-rules create fraud-digest-forwarding-rule --address=fraud-digest-ip --target-https-proxy=fraud-digest-https-proxy --ports=443 --global

# 7. Включение IAP на Бэкенд-сервисе
gcloud compute backend-services update fraud-digest-backend --iap=enabled --global

# 8. Финальная настройка сервиса Cloud Run для работы с Балансировщиком
gcloud run services update fraud-digest-weekly-app --ingress=internal-and-cloud-load-balancing
```

### 3.5. Настройка Backend (Pub/Sub и Секреты)
```powershell
# Создание Pub/Sub темы
gcloud pubsub topics create analysis-requests

# Создание секрета для Resend API ключа
echo "<YOUR_RESEND_API_KEY>" | gcloud secrets create RESEND_API_KEY --project=fraud-digest-app-v2-469310 --data-file=-
```

### 3.6. Настройка CI/CD (GitHub Actions)
```powershell
# Создание сервисного аккаунта для CI/CD
gcloud iam service-accounts create github-actions-deployer --display-name="GitHub Actions Deployer"

# Создание Пула и Провайдера Workload Identity
gcloud iam workload-identity-pools create "github-pool" --location="global" --display-name="GitHub Actions Pool"
gcloud iam workload-identity-pools providers create-oidc "github-provider" --location="global" --workload-identity-pool="github-pool" --display-name="GitHub Actions Provider" --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" --attribute-condition="assertion.repository == 'mayafudimaxionym/The-Fraud-Digest-Weekly-app'" --issuer-uri="https://token.actions.githubusercontent.com"

# Получение номера проекта
$PROJECT_NUMBER = gcloud projects describe fraud-digest-app-v2-469310 --format="value(projectNumber)"

# Связывание GitHub с сервисным аккаунтом
gcloud iam service-accounts add-iam-policy-binding "github-actions-deployer@fraud-digest-app-v2-469310.iam.gserviceaccount.com" --role="roles/iam.workloadIdentityUser" --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/mayafudimaxionym/The-Fraud-Digest-Weekly-app"

# Предоставление всех необходимых прав сервисному аккаунту CI/CD
gcloud projects add-iam-policy-binding fraud-digest-app-v2-469310 --member="serviceAccount:github-actions-deployer@fraud-digest-app-v2-469310.iam.gserviceaccount.com" --role="roles/run.developer"
gcloud projects add-iam-policy-binding fraud-digest-app-v2-469310 --member="serviceAccount:github-actions-deployer@fraud-digest-app-v2-469310.iam.gserviceaccount.com" --role="roles/iam.serviceAccountUser"
gcloud projects add-iam-policy-binding fraud-digest-app-v2-469310 --member="serviceAccount:github-actions-deployer@fraud-digest-app-v2-469310.iam.gserviceaccount.com" --role="roles/cloudfunctions.developer"
gcloud projects add-iam-policy-binding fraud-digest-app-v2-469310 --member="serviceAccount:github-actions-deployer@fraud-digest-app-v2-469310.iam.gserviceaccount.com" --role="roles/cloudbuild.builds.editor"
gcloud projects add-iam-policy-binding fraud-digest-app-v2-469310 --member="serviceAccount:github-actions-deployer@fraud-digest-app-v2-469310.iam.gserviceaccount.com" --role="roles/storage.admin"
gcloud projects add-iam-policy-binding fraud-digest-app-v2-469310 --member="serviceAccount:github-actions-deployer@fraud-digest-app-v2-469310.iam.gserviceaccount.com" --role="roles/eventarc.admin"
gcloud projects add-iam-policy-binding fraud-digest-app-v2-469310 --member="serviceAccount:github-actions-deployer@fraud-digest-app-v2-469310.iam.gserviceaccount.com" --role="roles/aiplatform.user"
gcloud projects add-iam-policy-binding fraud-digest-app-v2-469310 --member="serviceAccount:github-actions-deployer@fraud-digest-app-v2-469310.iam.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"

# Создание сервисного аккаунта для триггера Eventarc
gcloud iam service-accounts create eventarc-trigger-sa --display-name="Eventarc Trigger Service Account"

# Предоставление прав триггеру на вызов Cloud Run
gcloud run services add-iam-policy-binding fraud-analysis-processor-v2 --region=europe-west1 --member="serviceAccount:eventarc-trigger-sa@fraud-digest-app-v2-469310.iam.gserviceaccount.com" --role="roles/run.invoker"
```

### 3.7. Команды для отладки и обслуживания
```powershell
# Очистка "зависших" сообщений в подписке Pub/Sub
gcloud pubsub subscriptions seek (gcloud eventarc triggers describe fraud-analysis-processor-v2-trigger --project=fraud-digest-app-v2-469310 --location=europe-west1 --format="value(transport.pubsub.subscription)") --time=$(Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")

# Отправка тестового сообщения в Pub/Sub
gcloud pubsub topics publish analysis-requests --project=fraud-digest-app-v2-469310 --message='{"url": "https://www.bbc.com/news", "email": "maya.fudim@axionym.com"}'```

***