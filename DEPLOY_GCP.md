# Google Cloud Deployment Guide

This document describes a practical Google Cloud deployment path for the current project.
It is aligned with the repository state verified on `2026-04-01`.

Recommended target:

- staging
- internal demo
- limited pilot

Current verified baseline:

- Full regression suite: `286 passed, 2 warnings`
- Deployment regression suite: `120 passed`
- Backend import check: pass
- Frontend production build: passing
- Frontend lint: failing with `161 errors` and `194 warnings`

## Public API Path

The backend app itself registers root routes such as `/webhooks/stripe`.
That means the direct app-path form is:

```text
https://your-backend-domain.com/webhooks/stripe
```

Use the `/api/v1/...` form only if a proxy explicitly rewrites that prefix.

## Frontend Cloud Run

Recommended environment:

```env
NEXT_PUBLIC_API_URL=https://your-backend-domain.com
```

Build command:

```bash
cd frontend
npm install
npm run lint
npm run build
```

Current status:

- `npm run build`: passing
- `npm run lint`: failing

## Rollout Gate

Before promoting beyond staging, verify all of these:

- migrations succeed
- deployment regression suite passes at `120 passed`
- frontend production build remains green
- uploads work end-to-end
- approval notification path works
- review / social / calls / ROI routes behave per authenticated location
- Stripe duplicate webhook deliveries are deduped
- Twilio webhook routes respond correctly if enabled
- public API path convention is normalized across frontend, Stripe, Twilio, docs, and scripts

## Known Limits

This guide does not claim the product is ready for broad public self-serve production at scale.
It remains a controlled rollout guide until lint debt, path normalization, and operator support readiness are reduced.
