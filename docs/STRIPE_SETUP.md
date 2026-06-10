# Stripe Setup Guide

This guide covers the current Stripe setup expected by the codebase as verified on `2026-04-01`.

## 1. Stripe Dashboard Setup

### Products to Create

Create the following products in Stripe Dashboard.

#### Plans

| Product Name | Price ID Variable | Monthly | Yearly |
|-------------|-------------------|---------|--------|
| Starter | `STRIPE_PRICE_STARTER_*` | $99/mo | $990/yr |
| Pro | `STRIPE_PRICE_PRO_*` | $149/mo | $1,490/yr |
| Premium | `STRIPE_PRICE_PREMIUM_*` | $249/mo | $2,490/yr |
| Agency | `STRIPE_PRICE_AGENCY_*` | $499/mo/location | $4,990/yr/location |

#### Add-ons

| Add-on Name | Price ID Variable | Price |
|-------------|-------------------|-------|
| Missed Call Text Back | `STRIPE_PRICE_ADDON_MCB` | $29/mo |
| Review Booster | `STRIPE_PRICE_ADDON_RB` | $39/mo |
| Website SEO Upgrade | `STRIPE_PRICE_ADDON_SEO` | $49/mo |
| Social Auto-Responder | `STRIPE_PRICE_ADDON_SAR` | $29/mo |
| Video Generator | `STRIPE_PRICE_ADDON_VIDEO` | $49/mo |

## 2. Environment Variables

```bash
STRIPE_SECRET_KEY=sk_test_your_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_secret_here

STRIPE_PRICE_STARTER_MONTHLY=price_xxx
STRIPE_PRICE_STARTER_YEARLY=price_xxx
STRIPE_PRICE_PRO_MONTHLY=price_xxx
STRIPE_PRICE_PRO_YEARLY=price_xxx
STRIPE_PRICE_PREMIUM_MONTHLY=price_xxx
STRIPE_PRICE_PREMIUM_YEARLY=price_xxx
STRIPE_PRICE_AGENCY_MONTHLY=price_xxx
STRIPE_PRICE_AGENCY_YEARLY=price_xxx

STRIPE_PRICE_ADDON_MCB=price_xxx
STRIPE_PRICE_ADDON_RB=price_xxx
STRIPE_PRICE_ADDON_SEO=price_xxx
STRIPE_PRICE_ADDON_SAR=price_xxx
STRIPE_PRICE_ADDON_VIDEO=price_xxx
```

## 3. Webhook Setup

### Canonical App Route

The FastAPI app itself registers this route:

```text
/webhooks/stripe
```

Legacy compatibility route:

```text
/billing/webhook
```

Deprecated route:

```text
/webhooks/stripe-legacy
```

Do not use the legacy route for new Stripe configuration.

### Public URL Decision

If you expose the backend directly, use:

```text
https://your-backend-domain.com/webhooks/stripe
```

If you intentionally publish the API behind an ingress that rewrites `/api/v1 -> /`, then the public URL may be:

```text
https://your-domain.com/api/v1/webhooks/stripe
```

Only use the `/api/v1/...` form if that rewrite rule is explicit and documented.

### Required Events

Configure the webhook for at least:

- `checkout.session.completed`
- `checkout.session.expired`
- `checkout.session.async_payment_failed`
- `charge.refunded`
- `invoice.payment_failed`
- `invoice.payment_succeeded`
- `customer.subscription.updated`
- `customer.subscription.deleted`

### Local Development

```bash
stripe login
stripe listen --forward-to localhost:8000/webhooks/stripe
```

## 4. Operational Idempotency Check

The current canonical Stripe webhook route is designed to be idempotent.

Current protected app route:

```text
POST /webhooks/stripe
```

What to verify before production rollout:

- [ ] duplicate Stripe deliveries do not create duplicate side effects
- [ ] duplicate `event_id` values are stored once in `stripe_events`
- [ ] processing failures still leave an event record for audit and manual replay decisions
- [ ] Stripe retries do not re-run already processed events

Regression reference:

- webhook idempotency is covered by `tests/test_p0_webhook_idempotency.py`

## 5. Testing

### Test Cards

| Card Number | Description |
|-------------|-------------|
| `4242424242424242` | Successful payment |
| `4000000000000002` | Card declined |
| `4000002500003155` | Requires 3D Secure |
| `4000000000009995` | Insufficient funds |

### Test Flow

1. user starts trial or upgrade flow
2. checkout completes
3. webhook reaches the chosen public Stripe path
4. invoice/payment events are processed
5. duplicate delivery is safely ignored

### Quick Verification

Use the direct app route locally:

```bash
curl -X POST http://localhost:8000/webhooks/stripe \
  -H "Content-Type: application/json" \
  -H "Stripe-Signature: test" \
  -d '{"type": "test"}'
```

## 6. Production Checklist

- [ ] switch to live Stripe keys
- [ ] confirm the public webhook URL matches the chosen path convention
- [ ] confirm webhook signing secret matches backend config
- [ ] confirm idempotency test coverage is passing in CI or predeploy
- [ ] confirm dunning flow is configured
- [ ] confirm checkout and subscription lifecycle succeed end-to-end

## 7. Monitoring

Check:

- Stripe Dashboard payments and subscriptions
- webhook delivery logs in Stripe Dashboard
- backend logs for webhook processing results
- duplicate event handling behavior

## 8. Common Failure Modes

**Webhook not receiving events**

- verify endpoint URL
- verify public reachability
- verify secret matches backend config
- verify path convention is the same in Stripe, backend, docs, and ingress

**Subscription not updating**

- inspect webhook logs first
- confirm event is reaching the chosen public Stripe path
- confirm DB subscription mapping exists

**Duplicate side effects**

- inspect `stripe_events`
- confirm event ids are unique and stored once
- verify deployment did not route Stripe to the wrong endpoint by mistake
