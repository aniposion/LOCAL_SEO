# 🚀 Local SEO Optimizer 배포 가이드 (Google Cloud)

## 아키텍처
```
┌─────────────────────┐     ┌─────────────────────────────────────┐
│   A계정 (기존)       │     │   B계정 (신규)                       │
├─────────────────────┤     ├─────────────────────────────────────┤
│  ┌───────────────┐  │     │  ┌─────────────┐  ┌─────────────┐  │
│  │  Cloud SQL    │◄─┼─────┼──│ Cloud Run   │  │ Cloud Run   │  │
│  │  PostgreSQL   │  │     │  │ (Backend)   │  │ (Frontend)  │  │
│  │  us-central1  │  │     │  └─────────────┘  └─────────────┘  │
│  └───────────────┘  │     │         │                          │
└─────────────────────┘     │         ▼                          │
                            │  ┌─────────────┐  ┌─────────────┐  │
                            │  │   Cloud     │  │  Secret     │  │
                            │  │  Storage    │  │  Manager    │  │
                            │  └─────────────┘  └─────────────┘  │
                            └─────────────────────────────────────┘
```

## 목차
1. [사전 준비](#1-사전-준비)
2. [A계정 - Cloud SQL 설정](#2-a계정---cloud-sql-설정)
3. [B계정 - 프로젝트 설정](#3-b계정---프로젝트-설정)
4. [GitHub 저장소 연결](#4-github-저장소-연결)
5. [Cloud Run 배포](#5-cloud-run-배포)
6. [배포 후 설정](#6-배포-후-설정)

---

## 1. 사전 준비

### 필수 계정 및 API 키
| 서비스 | 필수 | 용도 | 발급처 |
|--------|------|------|--------|
| **Google Cloud A계정** | ✅ | Cloud SQL (기존) | - |
| **Google Cloud B계정** | ✅ | Cloud Run, Storage | console.cloud.google.com |
| **GitHub** | ✅ | 소스 코드 저장 | github.com |
| **Stripe** | ✅ | 결제 시스템 | stripe.com |
| **OpenAI** | ✅ | AI 콘텐츠 생성 | openai.com |
| Twilio | ⚪ | SMS (Missed Call) | twilio.com |

### 로컬에서 빌드 테스트
```bash
# 백엔드 테스트
cd local-seo-optimizer
pip install -r requirements.txt
python -c "from app.main import app; print('Backend OK')"

# 프론트엔드 빌드 테스트
cd frontend
npm install
npm run build
```

---

## 2. A계정 - Cloud SQL 설정

> 기존 Cloud SQL (us-central1, PostgreSQL 17.6) 사용

### 2.1 데이터베이스 생성
Cloud SQL 콘솔 또는 Cloud Shell에서:
```sql
-- 데이터베이스 생성
CREATE DATABASE local_seo_optimizer;

-- 사용자 생성
CREATE USER seo_app WITH PASSWORD 'your-secure-password-here';

-- 권한 부여
GRANT ALL PRIVILEGES ON DATABASE local_seo_optimizer TO seo_app;

-- 스키마 권한 (PostgreSQL 15+)
\c local_seo_optimizer
GRANT ALL ON SCHEMA public TO seo_app;
```

### 2.2 네트워크 설정 (공개 IP)
1. Cloud SQL 인스턴스 → **연결** → **네트워킹**
2. **승인된 네트워크** 추가:
   - 이름: `cloud-run-all` (임시, 나중에 제한)
   - 네트워크: `0.0.0.0/0`
3. **공개 IP 주소** 메모 (예: `34.xxx.xxx.xxx`)

### 2.3 연결 정보 확인
```
HOST: 34.xxx.xxx.xxx (공개 IP)
PORT: 5432
DATABASE: local_seo_optimizer
USER: seo_app
PASSWORD: your-secure-password-here
```

---

## 3. B계정 - 프로젝트 설정

### 3.1 새 프로젝트 생성
1. [Google Cloud Console](https://console.cloud.google.com) 접속 (B계정)
2. **프로젝트 선택** → **새 프로젝트**
3. 이름: `local-seo-optimizer`
4. **만들기**

### 3.2 API 활성화
Cloud Shell 또는 터미널에서:
```bash
# 프로젝트 설정
gcloud config set project YOUR_PROJECT_ID

# 필요한 API 활성화
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  artifactregistry.googleapis.com
```

### 3.3 Cloud Storage 버킷 생성
```bash
# 버킷 생성 (이름은 전역적으로 고유해야 함)
gsutil mb -l us-central1 gs://local-seo-optimizer-files

# CORS 설정 (프론트엔드에서 업로드 허용)
cat > cors.json << EOF
[
  {
    "origin": ["*"],
    "method": ["GET", "POST", "PUT", "DELETE"],
    "responseHeader": ["Content-Type"],
    "maxAgeSeconds": 3600
  }
]
EOF
gsutil cors set cors.json gs://local-seo-optimizer-files
```

### 3.4 Secret Manager에 비밀 저장
```bash
# JWT 시크릿
echo -n "your-super-secret-jwt-key-minimum-32-characters" | \
  gcloud secrets create jwt-secret --data-file=-

# Database URL
echo -n "postgresql+psycopg2://seo_app:password@34.xxx.xxx.xxx:5432/local_seo_optimizer?sslmode=require" | \
  gcloud secrets create database-url --data-file=-

# Stripe Secret Key
echo -n "sk_live_xxxxx" | \
  gcloud secrets create stripe-secret-key --data-file=-

# Stripe Webhook Secret
echo -n "whsec_xxxxx" | \
  gcloud secrets create stripe-webhook-secret --data-file=-

# OpenAI API Key
echo -n "sk-xxxxx" | \
  gcloud secrets create openai-api-key --data-file=-
```

### 3.5 서비스 계정 권한 설정
```bash
# Cloud Run 서비스 계정에 Secret 접근 권한 부여
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')

gcloud secrets add-iam-policy-binding jwt-secret \
  --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding database-url \
  --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding stripe-secret-key \
  --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding stripe-webhook-secret \
  --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding openai-api-key \
  --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## 4. GitHub 저장소 연결

### 4.1 GitHub에 코드 푸시
```bash
cd local-seo-optimizer

# Git 초기화 (이미 되어있다면 스킵)
git init
git add .
git commit -m "Initial commit"

# GitHub 저장소 생성 후 연결
git remote add origin https://github.com/YOUR_USERNAME/local-seo-optimizer.git
git branch -M main
git push -u origin main
```

### 4.2 Cloud Build 연결
1. [Cloud Build](https://console.cloud.google.com/cloud-build/triggers) 이동
2. **저장소 연결** → **GitHub** 선택
3. 저장소 `local-seo-optimizer` 선택
4. **연결**

---

## 5. Cloud Run 배포

### 5.1 Backend 배포

**방법 A: Cloud Console (GUI)**
1. [Cloud Run](https://console.cloud.google.com/run) 이동
2. **서비스 만들기**
3. **GitHub에서 지속적으로 배포** 선택
4. 설정:
   - 저장소: `local-seo-optimizer`
   - 브랜치: `main`
   - Dockerfile 경로: `/Dockerfile`
5. **리전**: `us-central1` (DB와 동일)
6. **인증**: 인증되지 않은 호출 허용
7. **환경 변수**:
   ```
   APP_ENV=production
   DEBUG=false
   GCS_BUCKET=local-seo-optimizer-files
   APP_URL=https://api.your-domain.com
   ```
8. **비밀**:
   - `DATABASE_URL` → `database-url:latest`
   - `JWT_SECRET` → `jwt-secret:latest`
   - `STRIPE_SECRET_KEY` → `stripe-secret-key:latest`
   - `STRIPE_WEBHOOK_SECRET` → `stripe-webhook-secret:latest`
   - `OPENAI_API_KEY` → `openai-api-key:latest`

**방법 B: 명령어**
```bash
gcloud run deploy local-seo-api \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "APP_ENV=production,DEBUG=false,GCS_BUCKET=local-seo-optimizer-files" \
  --set-secrets "DATABASE_URL=database-url:latest,JWT_SECRET=jwt-secret:latest,STRIPE_SECRET_KEY=stripe-secret-key:latest,OPENAI_API_KEY=openai-api-key:latest"
```

### 5.2 Frontend 배포

1. **서비스 만들기** (Cloud Run)
2. 설정:
   - 저장소: `local-seo-optimizer`
   - Dockerfile 경로: `/frontend/Dockerfile`
3. **환경 변수**:
   ```
   NEXT_PUBLIC_API_URL=https://local-seo-api-xxxxx-uc.a.run.app
   ```

또는 명령어:
```bash
cd frontend
gcloud run deploy local-seo-frontend \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "NEXT_PUBLIC_API_URL=https://local-seo-api-xxxxx-uc.a.run.app"
```

### 5.3 커스텀 도메인 설정 (선택)
1. Cloud Run → 서비스 선택 → **도메인 매핑**
2. **매핑 추가** → 도메인 입력
3. DNS에 CNAME 레코드 추가

---

## 6. 배포 후 설정

### 6.1 데이터베이스 마이그레이션
```bash
# Cloud Shell 또는 로컬에서
DATABASE_URL="postgresql+psycopg2://seo_app:password@34.xxx.xxx.xxx:5432/local_seo_optimizer?sslmode=require"
alembic upgrade head
```

### 6.2 Stripe Webhook 설정
1. [Stripe Dashboard](https://dashboard.stripe.com/webhooks) → Webhooks
2. **엔드포인트 추가**
3. URL: `https://local-seo-api-xxxxx-uc.a.run.app/api/v1/billing/webhook`
4. 이벤트 선택:
   - `checkout.session.completed`
   - `invoice.paid`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
5. **Signing secret** 복사 → Secret Manager 업데이트

### 6.3 기능 테스트 체크리스트
- [ ] 홈페이지 접속: `https://your-frontend-url`
- [ ] 회원가입: `/signup`
- [ ] 로그인: `/login`
- [ ] 온보딩: `/onboarding`
- [ ] 대시보드: `/dashboard`
- [ ] Stripe 테스트 결제 (카드: `4242 4242 4242 4242`)

### 6.4 CORS 설정 확인
Backend `app/main.py`에 프론트엔드 도메인 추가:
```python
origins = [
    "http://localhost:3000",
    "https://local-seo-frontend-xxxxx-uc.a.run.app",
    "https://your-custom-domain.com",
]
```

---

## 📋 환경 변수 요약

### Backend (Cloud Run)
| 변수명 | 값 | 타입 |
|--------|-----|------|
| `APP_ENV` | `production` | 환경변수 |
| `DEBUG` | `false` | 환경변수 |
| `GCS_BUCKET` | `local-seo-optimizer-files` | 환경변수 |
| `APP_URL` | `https://api.your-domain.com` | 환경변수 |
| `DATABASE_URL` | Secret Manager | 비밀 |
| `JWT_SECRET` | Secret Manager | 비밀 |
| `STRIPE_SECRET_KEY` | Secret Manager | 비밀 |
| `STRIPE_WEBHOOK_SECRET` | Secret Manager | 비밀 |
| `OPENAI_API_KEY` | Secret Manager | 비밀 |

### Frontend (Cloud Run)
| 변수명 | 값 |
|--------|-----|
| `NEXT_PUBLIC_API_URL` | `https://local-seo-api-xxxxx-uc.a.run.app` |

---

## 💰 예상 비용 (월간, B계정)

| 서비스 | 무료 티어 | 예상 비용 |
|--------|-----------|-----------|
| Cloud Run | 200만 요청 | $0-20 |
| Cloud Storage | 5GB | $0-5 |
| Secret Manager | 6개 비밀 | $0.06 |
| Cloud Build | 120분/일 | $0 |
| **합계** | - | **$0-25** |

> A계정 Cloud SQL ($100/월)은 기존 비용으로 별도

---

## 🆘 문제 해결

### Cloud Run 배포 실패
```bash
# 로그 확인
gcloud run services logs read local-seo-api --region us-central1
```

### 데이터베이스 연결 오류
1. A계정 Cloud SQL → 연결 → 승인된 네트워크 확인
2. `?sslmode=require` 추가 여부 확인
3. 방화벽 규칙 확인

### Secret Manager 접근 오류
```bash
# 서비스 계정 권한 확인
gcloud secrets get-iam-policy jwt-secret
```

### CORS 오류
- Backend의 `origins` 목록에 프론트엔드 URL 추가
- 재배포 필요

---

## 📞 배포 지원

문제 발생 시:
1. Cloud Run 로그 확인
2. 이 가이드의 문제 해결 섹션 참조
3. [Google Cloud 문서](https://cloud.google.com/run/docs)
