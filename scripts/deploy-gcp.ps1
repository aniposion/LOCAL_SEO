# Google Cloud 배포 스크립트 (PowerShell)
# 사용법: .\scripts\deploy-gcp.ps1 -ProjectId "your-project-id"

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectId,
    
    [string]$Region = "us-central1",
    [string]$AppUrl = "",
    [string]$AuthCookiePath = "/",
    [string]$EmailFrom = "noreply@localseo.app",
    [string]$SendGridFromEmail = "",
    [string]$TwilioPhoneNumber = "",
    [string]$GcsBucket = "",
    [string]$GcsProjectId = "",
    [string]$LlmProvider = "gemini",
    [string]$LlmModel = "gemini-1.5-pro"
)

function Join-EnvVars {
    param(
        [Parameter(Mandatory=$true)]
        [hashtable]$Values
    )

    return (($Values.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join ",")
}

Write-Host "🚀 Starting Google Cloud deployment..." -ForegroundColor Cyan

# 프로젝트 설정
Write-Host "Setting project to $ProjectId" -ForegroundColor Yellow
gcloud config set project $ProjectId

# API 활성화
Write-Host "Enabling required APIs..." -ForegroundColor Yellow
gcloud services enable `
    cloudbuild.googleapis.com `
    run.googleapis.com `
    secretmanager.googleapis.com `
    containerregistry.googleapis.com

$SecretBindings = "JWT_SECRET=jwt-secret:latest,STRIPE_SECRET_KEY=stripe-secret:latest,STRIPE_WEBHOOK_SECRET=stripe-webhook-secret:latest,OPENAI_API_KEY=openai-key:latest,GEMINI_API_KEY=gemini-key:latest,TWILIO_ACCOUNT_SID=twilio-account-sid:latest,TWILIO_AUTH_TOKEN=twilio-auth-token:latest,SENDGRID_API_KEY=sendgrid-api-key:latest,GBP_CLIENT_ID=gbp-client-id:latest,GBP_CLIENT_SECRET=gbp-client-secret:latest,IG_APP_ID=ig-app-id:latest,IG_APP_SECRET=ig-app-secret:latest"
$ResolvedSendGridFromEmail = if ([string]::IsNullOrWhiteSpace($SendGridFromEmail)) { $EmailFrom } else { $SendGridFromEmail }
$SharedRuntimeEnvVars = Join-EnvVars @{
    APP_ENV = "prod"
    AUTH_COOKIE_PATH = $AuthCookiePath
    EMAIL_FROM = $EmailFrom
    SENDGRID_FROM_EMAIL = $ResolvedSendGridFromEmail
    TWILIO_PHONE_NUMBER = $TwilioPhoneNumber
    GCS_BUCKET = $GcsBucket
    GCS_PROJECT_ID = $GcsProjectId
    LLM_PROVIDER = $LlmProvider
    LLM_MODEL = $LlmModel
}
$WorkerRuntimeEnvVars = Join-EnvVars @{
    APP_ENV = "prod"
    SCHEDULER_ENABLED = "true"
    SCHEDULER_TARGET = "all"
    AUTH_COOKIE_PATH = $AuthCookiePath
    EMAIL_FROM = $EmailFrom
    SENDGRID_FROM_EMAIL = $ResolvedSendGridFromEmail
    TWILIO_PHONE_NUMBER = $TwilioPhoneNumber
    GCS_BUCKET = $GcsBucket
    GCS_PROJECT_ID = $GcsProjectId
    LLM_PROVIDER = $LlmProvider
    LLM_MODEL = $LlmModel
}

# Backend 빌드 및 배포
Write-Host "Building backend Docker image..." -ForegroundColor Yellow
docker build -t "gcr.io/$ProjectId/local-seo-backend:latest" .

Write-Host "Pushing backend image..." -ForegroundColor Yellow
docker push "gcr.io/$ProjectId/local-seo-backend:latest"

Write-Host "Deploying backend to Cloud Run..." -ForegroundColor Yellow
gcloud run deploy local-seo-backend `
    --image "gcr.io/$ProjectId/local-seo-backend:latest" `
    --platform managed `
    --region $Region `
    --allow-unauthenticated `
    --memory 512Mi `
    --cpu 1 `
    --min-instances 0 `
    --max-instances 10 `
    --set-env-vars $SharedRuntimeEnvVars `
    --set-secrets $SecretBindings

Write-Host "Deploying scheduler worker to Cloud Run..." -ForegroundColor Yellow
gcloud run deploy local-seo-worker `
    --image "gcr.io/$ProjectId/local-seo-backend:latest" `
    --platform managed `
    --region $Region `
    --no-allow-unauthenticated `
    --command python `
    --args=-m,app.worker `
    --memory 512Mi `
    --cpu 1 `
    --min-instances 1 `
    --max-instances 1 `
    --no-cpu-throttling `
    --set-env-vars $WorkerRuntimeEnvVars `
    --set-secrets $SecretBindings

# Backend URL 가져오기
$BackendUrl = gcloud run services describe local-seo-backend --region $Region --format "value(status.url)"
$WorkerUrl = gcloud run services describe local-seo-worker --region $Region --format "value(status.url)"
Write-Host "Backend deployed at: $BackendUrl" -ForegroundColor Green
Write-Host "Worker deployed at: $WorkerUrl" -ForegroundColor Green

# Frontend 빌드 및 배포
Write-Host "Building frontend..." -ForegroundColor Yellow
Push-Location frontend

# 환경 변수 설정
$env:NEXT_PUBLIC_API_URL = $BackendUrl

npm ci
npm run build

Write-Host "Building frontend Docker image..." -ForegroundColor Yellow
docker build -t "gcr.io/$ProjectId/local-seo-frontend:latest" `
    --build-arg "NEXT_PUBLIC_API_URL=$BackendUrl" .

Write-Host "Pushing frontend image..." -ForegroundColor Yellow
docker push "gcr.io/$ProjectId/local-seo-frontend:latest"

Write-Host "Deploying frontend to Cloud Run..." -ForegroundColor Yellow
gcloud run deploy local-seo-frontend `
    --image "gcr.io/$ProjectId/local-seo-frontend:latest" `
    --platform managed `
    --region $Region `
    --allow-unauthenticated `
    --memory 256Mi `
    --cpu 1 `
    --min-instances 0 `
    --max-instances 10

Pop-Location

# Frontend URL 가져오기
$FrontendUrl = gcloud run services describe local-seo-frontend --region $Region --format "value(status.url)"
$ResolvedAppUrl = if ([string]::IsNullOrWhiteSpace($AppUrl)) { $FrontendUrl } else { $AppUrl }
$RuntimeAppUrlEnv = Join-EnvVars @{ APP_URL = $ResolvedAppUrl }

Write-Host "Updating backend APP_URL to $ResolvedAppUrl" -ForegroundColor Yellow
gcloud run services update local-seo-backend `
    --region $Region `
    --update-env-vars $RuntimeAppUrlEnv

Write-Host "Updating worker APP_URL to $ResolvedAppUrl" -ForegroundColor Yellow
gcloud run services update local-seo-worker `
    --region $Region `
    --update-env-vars $RuntimeAppUrlEnv

Write-Host ""
Write-Host "✅ Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "URLs:" -ForegroundColor Cyan
Write-Host "  Frontend: $FrontendUrl" -ForegroundColor White
Write-Host "  Backend:  $BackendUrl" -ForegroundColor White
Write-Host "  Worker:   $WorkerUrl" -ForegroundColor White
Write-Host ""
Write-Host "⚠️  Don't forget to:" -ForegroundColor Yellow
Write-Host "  1. Set up Cloud SQL for production database"
Write-Host "  2. Configure secrets in Secret Manager"
Write-Host "  3. Update CORS settings for production domains"
