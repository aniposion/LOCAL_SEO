# Google Cloud 배포 가이드

## 사전 준비

### 1. Google Cloud 프로젝트 설정

```bash
# Google Cloud SDK 설치 후 로그인
gcloud auth login

# 프로젝트 생성 또는 선택
gcloud projects create local-seo-optimizer --name="Local SEO Optimizer"
gcloud config set project local-seo-optimizer

# 필요한 API 활성화
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  containerregistry.googleapis.com
```

### 2. Cloud SQL (PostgreSQL) 설정

```bash
# PostgreSQL 인스턴스 생성
gcloud sql instances create local-seo-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1

# 데이터베이스 생성
gcloud sql databases create seo_optimizer --instance=local-seo-db

# 사용자 생성
gcloud sql users create seo_user \
  --instance=local-seo-db \
  --password=YOUR_SECURE_PASSWORD
```

### 3. Secret Manager 설정

```bash
# JWT Secret
echo -n "your-super-secret-jwt-key-minimum-32-chars-here" | \
  gcloud secrets create jwt-secret --data-file=-

# Stripe Secret Key
echo -n "sk_live_your_stripe_key" | \
  gcloud secrets create stripe-secret --data-file=-

# OpenAI API Key
echo -n "sk-your-openai-key" | \
  gcloud secrets create openai-key --data-file=-

# Google Places API Key
echo -n "your-google-places-api-key" | \
  gcloud secrets create google-places-key --data-file=-
```

## 배포 방법

### 방법 1: Cloud Build 자동 배포 (권장)

```bash
# Cloud Build 트리거 생성 (GitHub 연동)
gcloud builds triggers create github \
  --repo-name=local-seo-optimizer \
  --repo-owner=YOUR_GITHUB_USERNAME \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml \
  --substitutions=_DATABASE_URL="postgresql://seo_user:PASSWORD@/seo_optimizer?host=/cloudsql/PROJECT_ID:us-central1:local-seo-db"

# 수동 빌드 실행
gcloud builds submit \
  --config=cloudbuild.yaml \
  --substitutions=_DATABASE_URL="postgresql://seo_user:PASSWORD@/seo_optimizer?host=/cloudsql/PROJECT_ID:us-central1:local-seo-db"
```

### 방법 2: 수동 배포

#### Backend 배포

```bash
# Docker 이미지 빌드
docker build -t gcr.io/YOUR_PROJECT_ID/local-seo-backend .

# 이미지 푸시
docker push gcr.io/YOUR_PROJECT_ID/local-seo-backend

# Cloud Run 배포
gcloud run deploy local-seo-backend \
  --image gcr.io/YOUR_PROJECT_ID/local-seo-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --add-cloudsql-instances YOUR_PROJECT_ID:us-central1:local-seo-db \
  --set-env-vars "APP_ENV=prod" \
  --set-secrets "JWT_SECRET=jwt-secret:latest,STRIPE_SECRET_KEY=stripe-secret:latest,OPENAI_API_KEY=openai-key:latest,GBP_API_KEY=google-places-key:latest" \
  --set-env-vars "DATABASE_URL=postgresql://seo_user:PASSWORD@/seo_optimizer?host=/cloudsql/YOUR_PROJECT_ID:us-central1:local-seo-db"
```

#### Frontend 배포

```bash
cd frontend

# 환경 변수 설정 후 빌드
NEXT_PUBLIC_API_URL=https://local-seo-backend-XXXXX-uc.a.run.app npm run build

# Docker 이미지 빌드
docker build -t gcr.io/YOUR_PROJECT_ID/local-seo-frontend .

# 이미지 푸시
docker push gcr.io/YOUR_PROJECT_ID/local-seo-frontend

# Cloud Run 배포
gcloud run deploy local-seo-frontend \
  --image gcr.io/YOUR_PROJECT_ID/local-seo-frontend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

## 환경 변수

### Backend (.env.prod)
```
APP_ENV=prod
DATABASE_URL=postgresql://user:pass@/dbname?host=/cloudsql/project:region:instance
JWT_SECRET=<from-secret-manager>
STRIPE_SECRET_KEY=<from-secret-manager>
STRIPE_WEBHOOK_SECRET=<from-stripe-dashboard>
OPENAI_API_KEY=<from-secret-manager>
GBP_API_KEY=<from-secret-manager>
```

### Frontend
```
NEXT_PUBLIC_API_URL=https://local-seo-backend-xxxxx-uc.a.run.app
```

## 커스텀 도메인 설정

```bash
# Backend 도메인 매핑
gcloud run domain-mappings create \
  --service local-seo-backend \
  --domain api.yourdomain.com \
  --region us-central1

# Frontend 도메인 매핑
gcloud run domain-mappings create \
  --service local-seo-frontend \
  --domain app.yourdomain.com \
  --region us-central1
```

## 비용 예상 (월간)

| 서비스 | 예상 비용 |
|--------|----------|
| Cloud Run (Backend) | $5-20 |
| Cloud Run (Frontend) | $5-15 |
| Cloud SQL (db-f1-micro) | $10-15 |
| Secret Manager | $0.06 |
| Container Registry | $1-5 |
| **총계** | **$20-55/월** |

*트래픽에 따라 변동*

## 모니터링

```bash
# 로그 확인
gcloud run services logs read local-seo-backend --region us-central1

# 메트릭 확인
gcloud monitoring dashboards list
```

## 문제 해결

### Cloud SQL 연결 오류
```bash
# Cloud SQL Admin API 활성화 확인
gcloud services enable sqladmin.googleapis.com

# Cloud Run 서비스 계정에 Cloud SQL Client 역할 부여
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/cloudsql.client"
```

### Secret 접근 오류
```bash
# Secret Manager 접근 권한 부여
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```
