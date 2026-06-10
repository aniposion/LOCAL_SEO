# Deployment Guide

This guide reflects the repository state verified on `2026-04-01`.

Use it for:

- staging deployment
- internal demo deployment
- limited pilot deployment

It is not a claim that the product is ready for broad public self-serve production rollout.

## Current Verified Baseline

- Full regression suite: `pytest -q` -> `286 passed, 2 warnings`
- Deployment regression suite: `120 passed`
- Backend import check: `python -c "import app.main; print('ok')"` -> `ok`
- Frontend production build: passing
- Frontend lint: failing with `161 errors` and `194 warnings`

Current production blockers:

- frontend lint debt is still high
- public API path docs are still mixed between root routes and `/api/v1/...`
- billing / operator runbook depth is still limited for broad public self-serve support

## Public API Path

The FastAPI app currently registers unprefixed routes such as:

- `/auth/login`
- `/locations`
- `/metrics/dashboard`
- `/webhooks/stripe`

That means `/api/v1/...` is not a built-in application prefix.

Use one of these two conventions, and keep it consistent everywhere:

1. Direct app path

```text
https://your-backend-domain.com/webhooks/stripe
```

2. Proxy-prefixed path

```text
https://your-domain.com/api/v1/webhooks/stripe
```

Only use the proxy-prefixed form if an ingress or API gateway explicitly rewrites `/api/v1 -> /`.

## Frontend Deployment Steps

```bash
cd frontend
npm install
npm run lint
npm run build
npm run start
```

Current status:

- `npm run build`: passing
- `npm run lint`: failing

## Smoke Tests

Recommended script:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_test_prod.ps1 `
  -BackendBase https://your-backend-domain.com `
  -AccessToken "<JWT>"
```

If your public API is published behind `/api/v1`, pass `-ApiBase` explicitly.

## Recommended Rollout

1. deploy to staging
2. verify `/readyz`
3. run smoke tests
4. verify Stripe / Twilio / OAuth callback URLs
5. run limited pilot with a few locations
6. monitor webhook, approval, upload, Twilio, and billing failures
7. expand only after lint debt, path normalization, and operator support readiness improve
