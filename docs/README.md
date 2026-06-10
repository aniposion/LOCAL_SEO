# Local SEO Optimizer 문서 허브

작성일: `2026-03-06`  
최신 반영 기준: `2026-04-01`

## 현재 검증 상태

- 전체 테스트: `pytest -q` -> `286 passed, 2 warnings`
- 운영 배포 회귀 세트: `120 passed`
- backend import check: 통과
- frontend `npm run build`: 통과
- frontend `npm run lint`: 실패, 현재 `161 errors`, `194 warnings`
- 현재 rollout 허용 범위: `staging`, `internal demo`, `limited pilot`
- `broad public self-serve rollout`은 아직 보류

현재 production / commercialization blocker:

1. frontend lint debt
2. public API path 문서와 운영값 정렬
3. billing / operator runbook 강화

## production 문서 source of truth

- [DEPLOYMENT_CHECKLIST.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/DEPLOYMENT_CHECKLIST.md)
- [PRODUCTION_READINESS_CHECKLIST_KR_2026-03-06.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/PRODUCTION_READINESS_CHECKLIST_KR_2026-03-06.md)
- [PROD_LAUNCH_CHECKLIST_KR_2026-03-28.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/PROD_LAUNCH_CHECKLIST_KR_2026-03-28.md)
- [DEPLOYMENT_RISK_ASSESSMENT_KR_2026-03-06.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/DEPLOYMENT_RISK_ASSESSMENT_KR_2026-03-06.md)
- [OPERATIONS_RUNBOOK_KR_2026-03-06.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/OPERATIONS_RUNBOOK_KR_2026-03-06.md)
- [STRIPE_SETUP.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/STRIPE_SETUP.md)
- [PRODUCT_COMMERCIALIZATION_CHECKLIST_KR_2026-03-27.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/PRODUCT_COMMERCIALIZATION_CHECKLIST_KR_2026-03-27.md)
- [MONETIZATION_READINESS_AUDIT_v2.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/MONETIZATION_READINESS_AUDIT_v2.md)
- [DEPLOYMENT_GUIDE.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/DEPLOYMENT_GUIDE.md)
- [DEPLOY_GCP.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/DEPLOY_GCP.md)
- [GCP_BOOTSTRAP_CHECKLIST_KR_2026-04-01.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/GCP_BOOTSTRAP_CHECKLIST_KR_2026-04-01.md)
- [bootstrap-gcp.ps1](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/scripts/bootstrap-gcp.ps1)

## API path 주의사항

현재 FastAPI 앱은 `/auth`, `/locations`, `/metrics/dashboard`, `/webhooks/stripe`처럼 루트 경로를 직접 등록합니다.
즉, `/api/v1/...`는 앱 내부 기본 prefix가 아닙니다.

정리 원칙:

- direct app path를 쓸 경우 public URL도 루트 경로 기준으로 맞춥니다.
- `/api/v1/...`를 public URL로 쓸 경우 ingress 또는 proxy가 `/api/v1 -> /`를 명시적으로 rewrite해야 합니다.
- frontend `NEXT_PUBLIC_API_URL`, Stripe webhook, Twilio callback, 운영 문서가 모두 같은 기준을 따라야 합니다.

## smoke test 기준

`scripts/smoke_test_prod.ps1`는 현재 라우트 기준으로 갱신됐습니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_test_prod.ps1 `
  -BackendBase https://your-backend-domain.com `
  -AccessToken "<JWT>"
```

proxy prefix를 쓸 경우:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_test_prod.ps1 `
  -BackendBase https://your-backend-domain.com `
  -ApiBase https://your-domain.com/api/v1 `
  -AccessToken "<JWT>"
```

## 다음 우선순위

1. `frontend/src/lib/api.ts`, `stores/*`, onboarding / billing / usage 계열 lint 부채 정리
2. `/api/v1` 기준이 남아 있는 비운영 문서와 helper code 정리
3. Twilio / OAuth 실제 운영 runbook 보강
4. broad public rollout readiness 재평가
