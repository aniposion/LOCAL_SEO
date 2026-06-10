# GCP Bootstrap Checklist

작성일: `2026-04-01`  
대상 프로젝트: `local-seo-492020`  
현재 상태: GCP 프로젝트만 생성됨, Cloud Run 서비스 없음

이 문서는 이 repo를 새 GCP 프로젝트에 처음 올리기 전에 필요한 설정을 체크리스트로 정리한 문서다.  
기준 repo 상태는 현재 `cloudbuild.yaml`, `.env.example`, `app/core/config.py`를 따른다.

## 자동화 스크립트

- [bootstrap-gcp.ps1](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/scripts/bootstrap-gcp.ps1)
- 예시:

```powershell
.\scripts\bootstrap-gcp.ps1 `
  -ProjectId local-seo-492020 `
  -Region us-central1 `
  -CreateBucket `
  -BucketName local-seo-492020-assets `
  -IncludeCloudSqlApis `
  -GrantCurrentUserAdminRoles
```

## 기본 결정

- [ ] 기본 리전을 정한다. 권장: `us-central1`
- [ ] 서비스 이름을 그대로 쓸지 확정한다.
  - backend: `local-seo-backend`
  - frontend: `local-seo-frontend`
- [ ] 배포 전략을 정한다.
  - `Cloud Build + Cloud Run` 유지
  - 또는 수동 `gcloud run deploy`
- [ ] 운영 도메인 정책을 정한다.
  - frontend public URL
  - backend public URL
  - custom domain 사용 여부

## 1. 프로젝트 기본

- [ ] Billing 계정을 연결한다
- [ ] 프로젝트 소유자 / 운영자 계정을 추가한다
- [ ] 기본 프로젝트를 설정한다

```powershell
gcloud config set project local-seo-492020
```

## 2. 필수 API 활성화

필수:

- [ ] `run.googleapis.com`
- [ ] `cloudbuild.googleapis.com`
- [ ] `artifactregistry.googleapis.com`
- [ ] `secretmanager.googleapis.com`
- [ ] `storage.googleapis.com`

DB를 Cloud SQL로 운영할 경우 추가:

- [ ] `sqladmin.googleapis.com`

VPC / private IP 연결을 쓸 경우 추가:

- [ ] `vpcaccess.googleapis.com`
- [ ] `servicenetworking.googleapis.com`

예시:

```powershell
gcloud services enable `
  run.googleapis.com `
  cloudbuild.googleapis.com `
  artifactregistry.googleapis.com `
  secretmanager.googleapis.com `
  storage.googleapis.com `
  sqladmin.googleapis.com `
  --project local-seo-492020
```

## 3. IAM / 서비스 계정

권장 principal:

- 사람용 운영 계정
- Cloud Build 배포용 서비스 계정
- backend runtime 서비스 계정
- frontend runtime 서비스 계정

사람용 운영 계정에 필요한 권한:

- [ ] `roles/run.admin`
- [ ] `roles/cloudbuild.builds.editor`
- [ ] `roles/iam.serviceAccountUser`
- [ ] `roles/secretmanager.admin`
- [ ] `roles/serviceusage.serviceUsageAdmin`
- [ ] `roles/storage.admin`
- [ ] `roles/cloudsql.admin` (Cloud SQL 사용 시)

Cloud Build 배포 계정에 필요한 권한:

- [ ] `roles/run.admin`
- [ ] `roles/iam.serviceAccountUser`
- [ ] `roles/secretmanager.secretAccessor`
- [ ] `roles/storage.admin` 또는 최소 `roles/storage.objectAdmin`
- [ ] `roles/cloudsql.client` (Cloud SQL 사용 시)

backend runtime 서비스 계정에 필요한 권한:

- [ ] `roles/storage.objectAdmin` 또는 bucket 단위 쓰기 권한
- [ ] `roles/cloudsql.client` (Cloud SQL 사용 시)

frontend runtime 서비스 계정:

- [ ] 특별 권한 없음 또는 최소 권한만 부여

## 4. 데이터베이스

이 앱은 production에서 SQLite를 쓰면 안 된다. `DATABASE_URL`은 PostgreSQL 기준으로 준비해야 한다.

- [ ] PostgreSQL 인스턴스를 준비한다
  - Cloud SQL 또는 외부 PostgreSQL
- [ ] DB 이름을 만든다
- [ ] DB 사용자 / 비밀번호를 만든다
- [ ] `DATABASE_URL`을 만든다
- [ ] backend가 해당 DB에 네트워크로 접근 가능한지 확인한다
- [ ] 첫 배포 후 `alembic upgrade head`를 실행할 계획을 잡는다

예시 형식:

```text
postgresql+psycopg2://USER:PASSWORD@HOST:5432/DB_NAME
```

결정 필요:

- [ ] Cloud SQL public IP로 단순 연결
- [ ] private IP + Serverless VPC Access
- [ ] 외부 managed PostgreSQL 사용

## 5. 스토리지

업로드 / 카드 생성 / 파일 보관 기능을 쓰려면 cloud storage가 필요하다.

- [ ] GCS bucket 생성
- [ ] backend runtime 서비스 계정에 bucket 권한 부여
- [ ] `GCS_BUCKET` 값 확정
- [ ] 필요하면 `GCS_PROJECT_ID`도 설정

선택:

- [ ] S3를 대신 쓸 경우 `S3_BUCKET`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

## 6. Secret / 환경변수

### backend 최소 필수

- [ ] `APP_ENV=prod`
- [ ] `DEBUG=false`
- [ ] `DATABASE_URL`
- [ ] `JWT_SECRET`
- [ ] `APP_URL`

### frontend 최소 필수

- [ ] `NEXT_PUBLIC_API_URL`

### AI 기능

둘 중 하나는 반드시 준비:

- [ ] `OPENAI_API_KEY`
- [ ] `GEMINI_API_KEY`

또는 provider 결정:

- [ ] `LLM_PROVIDER=openai`
- [ ] `LLM_PROVIDER=gemini`

### 결제 기능 사용 시

- [ ] `STRIPE_SECRET_KEY`
- [ ] `STRIPE_WEBHOOK_SECRET`
- [ ] plan price id
  - `STRIPE_PRICE_STARTER_MONTHLY`
  - `STRIPE_PRICE_STARTER_YEARLY`
  - `STRIPE_PRICE_PRO_MONTHLY`
  - `STRIPE_PRICE_PRO_YEARLY`
  - `STRIPE_PRICE_PREMIUM_MONTHLY`
  - `STRIPE_PRICE_PREMIUM_YEARLY`
  - `STRIPE_PRICE_AGENCY_MONTHLY`
  - `STRIPE_PRICE_AGENCY_YEARLY`
- [ ] add-on price id
  - `STRIPE_PRICE_ADDON_MCB`
  - `STRIPE_PRICE_ADDON_RB`
  - `STRIPE_PRICE_ADDON_SEO`
  - `STRIPE_PRICE_ADDON_SAR`
  - `STRIPE_PRICE_ADDON_VIDEO`

### OAuth / 채널 기능 사용 시

- [ ] `GBP_CLIENT_ID`
- [ ] `GBP_CLIENT_SECRET`
- [ ] `GBP_API_KEY` (사용 시)
- [ ] `IG_APP_ID`
- [ ] `IG_APP_SECRET`

### 알림 / 통신 기능 사용 시

- [ ] `TWILIO_ACCOUNT_SID`
- [ ] `TWILIO_AUTH_TOKEN`
- [ ] `TWILIO_PHONE_NUMBER`
- [ ] `SENDGRID_API_KEY`
- [ ] `SENDGRID_FROM_EMAIL`
- [ ] `SMTP_*` 또는 `SLACK_WEBHOOK_URL` / `SENTRY_DSN` (선택)

## 7. Secret Manager 권장 이름

현재 `cloudbuild.yaml` 기준으로 이미 기대하고 있는 이름:

- [ ] `jwt-secret`
- [ ] `stripe-secret`
- [ ] `openai-key`

추가 권장:

- [ ] `stripe-webhook-secret`
- [ ] `gemini-key`
- [ ] `twilio-account-sid`
- [ ] `twilio-auth-token`
- [ ] `sendgrid-api-key`
- [ ] `gbp-client-id`
- [ ] `gbp-client-secret`
- [ ] `ig-app-id`
- [ ] `ig-app-secret`
- [ ] `database-url`

예시:

```powershell
echo -n "your-jwt-secret" | gcloud secrets create jwt-secret --data-file=-
```

## 8. 현재 repo 기준 주의점

이 repo는 지금 바로 배포해도 되는 형태로 완전히 정렬된 것은 아니다. 아래 항목은 배포 전에 결정하거나 수정해야 한다.

1. `cloudbuild.yaml`은 현재 backend에 다음만 secret 주입한다.
   - `JWT_SECRET`
   - `STRIPE_SECRET_KEY`
   - `OPENAI_API_KEY`

2. 그런데 앱 설정은 `gemini`도 지원하고, `.env.example` 기본 `LLM_PROVIDER`는 `gemini`다.
   - [ ] `OPENAI`로 갈지 `Gemini`로 갈지 먼저 결정
   - [ ] `GEMINI_API_KEY`를 쓸 경우 Cloud Build / Cloud Run env 주입 추가

3. Stripe billing을 켤 경우 `STRIPE_WEBHOOK_SECRET`가 필요하지만 현재 `cloudbuild.yaml`에는 없다.
   - [ ] Secret Manager에 만들기
   - [ ] backend deploy 시 주입 추가

4. 현재 `cloudbuild.yaml`은 `_DATABASE_URL` substitution을 사용한다.
   - [ ] 그대로 쓸지
   - [ ] Secret Manager의 `database-url`로 옮길지 결정

5. frontend는 `NEXT_PUBLIC_API_URL`이 backend 실제 Cloud Run URL과 반드시 같아야 한다.
   - 현재 repo는 backend deploy 후 `status.url`을 읽어 frontend build에 넣는 흐름으로 보정되어 있다.

## 9. 도메인 / CORS / 콜백

- [ ] `APP_URL` = frontend public URL 로 설정
- [ ] `NEXT_PUBLIC_API_URL` = backend public URL 로 설정
- [ ] frontend / backend 도메인 조합에 맞게 CORS 확인
- [ ] Stripe webhook endpoint 등록
  - canonical: `/webhooks/stripe`
- [ ] Twilio callback URL 확인
  - root path 기준 사용
- [ ] Google / Instagram OAuth redirect URI 등록

주의:

- 이 앱은 기본 prefix가 `/api/v1`가 아니다
- `/api/v1/...`를 외부에 노출하려면 ingress 또는 proxy가 rewrite 해야 한다

## 10. 첫 배포 전 체크

- [ ] `python -c "import app.main; print('ok')"` 통과
- [ ] backend test 회귀 세트 통과
- [ ] frontend `npm run build` 통과
- [ ] frontend `npm run lint`가 최소한 error-free 상태인지 확인
- [ ] Secret 이름 / env 이름 / 실제 프로젝트 값이 서로 일치하는지 확인

## 11. 첫 배포 순서

1. backend 배포
2. backend `status.url` 확인
3. frontend `NEXT_PUBLIC_API_URL`에 backend URL 주입
4. frontend 배포
5. Stripe / Twilio / OAuth callback 등록
6. smoke test 실행

## 12. 배포 후 확인

- [ ] Cloud Run에 `local-seo-backend` 생성 확인
- [ ] Cloud Run에 `local-seo-frontend` 생성 확인
- [ ] backend `/healthz`, `/readyz` 확인
- [ ] 로그인 / location 목록 / billing / notifications 주요 경로 확인
- [ ] `scripts/smoke_test_prod.ps1` 실행

예시:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_test_prod.ps1 `
  -BackendBase https://your-backend-domain.com `
  -AccessToken "<JWT>"
```

## 13. 지금 바로 필요한 최소 액션

프로젝트만 만든 현재 시점이라면 우선 이 순서가 가장 효율적이다.

1. 필수 API 활성화
2. Cloud Build / runtime 서비스 계정 권한 부여
3. PostgreSQL 준비 후 `DATABASE_URL` 확정
4. Secret Manager에 `jwt-secret`, `database-url`, `openai-key` 또는 `gemini-key` 생성
5. `APP_URL`, `NEXT_PUBLIC_API_URL` 정책 결정
6. backend first deploy
7. frontend deploy
8. smoke test
