# Google Cloud 배포 스크립트 (PowerShell)
# 사용법: .\scripts\deploy-gcp.ps1 -ProjectId "your-project-id"

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectId,
    
    [string]$Region = "us-central1"
)

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
    --max-instances 10

# Backend URL 가져오기
$BackendUrl = gcloud run services describe local-seo-backend --region $Region --format "value(status.url)"
Write-Host "Backend deployed at: $BackendUrl" -ForegroundColor Green

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

Write-Host ""
Write-Host "✅ Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "URLs:" -ForegroundColor Cyan
Write-Host "  Frontend: $FrontendUrl" -ForegroundColor White
Write-Host "  Backend:  $BackendUrl" -ForegroundColor White
Write-Host ""
Write-Host "⚠️  Don't forget to:" -ForegroundColor Yellow
Write-Host "  1. Set up Cloud SQL for production database"
Write-Host "  2. Configure secrets in Secret Manager"
Write-Host "  3. Update CORS settings for production domains"
