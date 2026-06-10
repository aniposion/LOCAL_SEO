# Local SEO Optimizer

Local SEO Optimizer는 지역 비즈니스의 Google Maps/GBP 운영, 리뷰 응답, 로컬 콘텐츠, missed-call 후속 문자, 리포팅, 결제를 한 흐름으로 묶는 managed local SEO 제품입니다.

## 현재 판매 판정

작성 기준: 2026-05-18

- 판매 가능: 5-10개 파일럿 고객 대상 managed 3개월 pilot.
- 판매 보류: 완전 무인 self-serve SaaS 공개 판매.
- 이유: 공개 가격, billing catalog, lead funnel, 실패 UX, 운영 runbook은 정렬되었지만 실제 staging/prod secret 주입과 full smoke는 운영 환경에서 완료해야 합니다.

## 공개 managed pilot 패키지

| Package ID | 이름 | 월 가격 | Setup | 판매 motion |
| --- | --- | ---: | ---: | --- |
| `maps_starter` | Maps Starter | $699/mo | $499 | 3-month managed pilot |
| `calls_growth` | Calls Growth | $999/mo | $799 | 3-month managed pilot |
| `competitive_market` | Competitive Market | $1,499/mo | $1,500 | 3-month managed pilot |

기존 `starter`, `pro`, `premium`, `agency` self-serve plan은 기존 고객과 내부 호환용 legacy catalog로 유지됩니다.

## 기술 스택

- Backend: FastAPI, SQLAlchemy, Alembic
- Frontend: Next.js, React, TypeScript
- Billing: Stripe Checkout, Stripe Billing Portal, webhook idempotency
- Integrations: Google Business Profile, Instagram, Twilio, SendGrid, cloud storage
- Database: PostgreSQL for staging/prod, SQLite only for local/dev tests

## 빠른 시작

Backend:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Production 환경변수

출시 전 `staging`과 `prod`에 최소한 아래 값을 채워야 합니다.

- Stripe: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, managed pilot `STRIPE_PRICE_*`
- Storage: `GCS_BUCKET` 또는 S3 관련 변수
- Google Business Profile: `GBP_CLIENT_ID`, `GBP_CLIENT_SECRET`
- Instagram: `IG_APP_ID`, `IG_APP_SECRET`
- Auth: placeholder가 아닌 `JWT_SECRET`
- Email: `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL`
- AI: `GEMINI_API_KEY` 또는 `OPENAI_API_KEY`

환경 점검:

```bash
python scripts/check_prod_env.py --require-prod
```

## 배포 검증

Migration:

```bash
alembic upgrade head
```

Production smoke:

```powershell
scripts/smoke_test_prod.ps1 -Profile full
```

`-Profile full`은 health/readiness, OAuth, upload, Twilio, Stripe, publish, admin, sales funnel 경로를 확인합니다. 실제 staging/prod URL, 테스트 계정, secret이 필요합니다.

## 주요 API 경로

- Public contact funnel: `POST /contact/requests`
- Admin contact queue: `GET /contact/requests`
- Admin sales summary: `GET /contact/summary`
- Public billing plans: `GET /billing/plans`
- Legacy billing plans: `GET /billing/plans?catalog=legacy`
- Stripe checkout: `POST /billing/checkout`
- Stripe webhook canonical route: `POST /webhooks/stripe`
- Compatibility API prefix: `/api/v1/...`

## 검증 명령

Backend:

```bash
pytest -q
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

## 핵심 문서

- [제품 개선 설계서](docs/PRODUCT_IMPROVEMENT_DESIGN_KR_2026-05-18.md)
- [제품 판매 readiness 체크리스트](docs/PRODUCT_READINESS_CHECKLIST_KR_2026-05-18.md)
- [Billing/Support/Incident Runbook](docs/BILLING_SUPPORT_INCIDENT_RUNBOOK_KR_2026-05-18.md)
- [Deployment Checklist](docs/DEPLOYMENT_CHECKLIST.md)
- [GCP Bootstrap Checklist](docs/GCP_BOOTSTRAP_CHECKLIST_KR_2026-04-01.md)

## Release branch 정리 원칙

현재 worktree에는 기존 변경과 untracked 파일이 많습니다. release branch 정리는 다음 원칙으로 진행합니다.

1. 기존 변경을 임의로 되돌리지 않습니다.
2. 이번 개선 범위의 변경 파일만 분리해 검토합니다.
3. generated/cache/local artifact는 별도 승인 후 정리합니다.
4. destructive cleanup은 `git status --short` 검토 후 사용자 승인 없이 실행하지 않습니다.
