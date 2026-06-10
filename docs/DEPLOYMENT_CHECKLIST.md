# Deployment Checklist - Current Production Gate

Verified on `2026-05-02`.

## Current Verified Baseline

- Operating + commercialization regression suite: `198 passed`
- Backend import check: `python -c "import app.main; print('ok')"` -> `ok`
- Backend OpenAPI generation check: `python -c "import app.main; app.main.app.openapi(); print('ok')"` -> `ok`
- `python scripts/check_prod_env.py` should still be run in the target env; local dev may report expected local-env warnings
- Frontend `npm run build` passes
- Frontend `npm run lint` passes
- `next build` also emits `baseline-browser-mapping` staleness warnings from frontend dev dependencies

This checklist is suitable for:

- staging
- internal demo
- limited pilot

It is not proof of broad public self-serve readiness.

## Current Production Blockers

- staging/production smoke tests still need to be run against real external URLs and provider callbacks
- billing / operator runbook depth is still limited for broad public self-serve support
- managed pilot pricing and self-serve checkout boundaries need an operator runbook before broad rollout

## Public API Path Decision

The FastAPI app registers unprefixed canonical routes such as:

- `/auth/login`
- `/locations`
- `/metrics/dashboard`
- `/webhooks/stripe`

The application also registers `/api/v1/...` compatibility aliases for the same routers.

Choose one public convention and keep it consistent everywhere:

- direct app path: `https://your-backend-domain.com/webhooks/stripe`
- proxy-prefixed path: `https://your-domain.com/api/v1/webhooks/stripe`

Use one public convention consistently across frontend `NEXT_PUBLIC_API_URL`, Stripe/Twilio/OAuth callbacks, and smoke checks.

## Smoke Test Script

`scripts/smoke_test_prod.ps1` has been refreshed for the current route model.

Direct app path example:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_test_prod.ps1 `
  -BackendBase https://your-backend-domain.com `
  -AccessToken "<JWT>"
```

Built-in `/api/v1` compatibility example:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_test_prod.ps1 `
  -BackendBase https://your-backend-domain.com `
  -ApiBase https://your-domain.com/api/v1 `
  -AccessToken "<JWT>"
```

Sales funnel smoke checks are included in `-Profile daily` and `-Profile full`. They validate `/api/v1/healthz`, contact form validation, and the admin contact queue when admin credentials are provided. To create a real smoke contact request, pass `-ContactTestEmail` or set `LSO_SMOKE_CONTACT_TEST_EMAIL`.

## Frontend Gate

```bash
cd frontend
npm run lint
npm run build
```

Current status:

- `npm run build`: passing
- `npm run lint`: passing

Launch expectation:

- [ ] `npm run build` remains green in CI / release flow
- [x] lint errors are reduced or explicitly triaged
- [ ] auth / onboarding / callback / dashboard routes are production-safe

## Rollout Verdict

Current recommendation on `2026-05-02`:

- `staging`: allowed
- `internal demo`: allowed
- `limited pilot`: allowed
- `broad public rollout`: hold
