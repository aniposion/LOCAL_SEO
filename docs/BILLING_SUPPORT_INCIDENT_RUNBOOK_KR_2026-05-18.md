# Billing, Support, Incident Runbook

작성일: 2026-05-18  
대상: managed pilot 운영자, support 담당자, release 담당자.

## 1. 결제 실패

고객 메시지:

```text
결제가 완료되지 않아 구독 확인이 지연되고 있습니다. Billing 화면에서 결제 수단을 업데이트해 주세요. 이미 결제하셨다면 Stripe 확인에 몇 분이 걸릴 수 있으니 잠시 후 새로고침해 주세요.
```

확인 순서:

1. Admin Recovery Console에서 dunning 상태를 확인한다.
2. Stripe customer id와 subscription id를 확인한다.
3. `/billing/webhook-events`에서 최근 `invoice.payment_failed` 또는 `checkout.session.completed` 이벤트를 확인한다.
4. 고객에게 billing portal 링크를 보낸다.
5. 동일 카드 실패가 반복되면 다른 결제수단을 요청한다.

Escalation:

- access가 `suspended`이고 고객이 결제 완료 영수증을 보유한 경우 Stripe dashboard와 webhook replay를 확인한다.
- webhook secret mismatch가 의심되면 `STRIPE_WEBHOOK_SECRET`과 endpoint URL을 즉시 확인한다.

## 2. Checkout 완료 후 플랜 미반영

확인 순서:

1. Stripe Checkout Session이 `complete`인지 확인한다.
2. session metadata에 `account_id`, `plan_type`, `billing_cycle`이 있는지 확인한다.
3. `customer.subscription.created` webhook이 들어왔는지 확인한다.
4. `subscriptions.stripe_subscription_id`, `stripe_price_id`, `plan_type` 갱신 여부를 확인한다.
5. webhook이 누락되었으면 Stripe에서 replay한다.

관련 managed plan id:

- `maps_starter`
- `calls_growth`
- `competitive_market`

## 3. 환불/취소

원칙:

- 환불은 Stripe에서 먼저 처리하고, 앱의 audit/refund log가 이를 반영하는지 확인한다.
- 취소는 고객이 원하는 경우 billing portal에서 처리하게 한다.
- managed pilot 계약 기간 중 예외 취소는 내부 승인 후 처리한다.

고객 메시지:

```text
요청하신 취소/환불 상태를 확인했습니다. Stripe 처리 상태를 확인한 뒤 영업일 기준으로 처리 예상 시간을 다시 안내드리겠습니다.
```

## 4. GBP OAuth 실패

고객 메시지:

```text
Google Business Profile 연결이 완료되지 않았습니다. Integrations 화면에서 다시 연결해 주세요. 같은 오류가 반복되면 연결하려는 Google 계정과 비즈니스 이름을 보내주시면 수동으로 확인하겠습니다.
```

확인 순서:

1. callback URL이 production backend URL을 사용 중인지 확인한다.
2. Google OAuth client의 redirect URI allowlist를 확인한다.
3. 요청 scope가 GBP API 권한과 일치하는지 확인한다.
4. 저장된 channel 상태가 `reconnect_required`, `expired`, `error`인지 확인한다.
5. 토큰 refresh가 가능한 경우 refresh를 먼저 시도한다.

## 5. Instagram OAuth 실패

확인 순서:

1. `IG_APP_ID`, `IG_APP_SECRET`이 staging/prod에 설정되었는지 확인한다.
2. Instagram/Facebook 앱의 redirect URI가 backend callback과 일치하는지 확인한다.
3. 고객 계정이 필요한 Instagram business/account 권한을 갖는지 확인한다.
4. Integrations callback 화면의 message를 support ticket에 복사한다.

## 6. Onboarding/Audit 실패

고객 메시지:

```text
자동 audit이 완료되지 않았지만 요청 정보는 확인할 수 있습니다. 다시 시도하시거나 contact sales로 보내주시면 수동으로 Google Maps 상태를 검토하겠습니다.
```

확인 순서:

1. `audit_id`가 contact request에 연결되었는지 확인한다.
2. Google Places/GBP API quota와 key 설정을 확인한다.
3. 같은 비즈니스로 재시도했을 때 candidate selection이 필요한지 확인한다.
4. 실패가 반복되면 contact request를 `booked`로 옮겨 manual review를 예약한다.

## 7. Email 장애

확인 순서:

1. `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL` 설정을 확인한다.
2. SendGrid sender/domain 인증 상태를 확인한다.
3. 앱 notification inbox에 fallback alert가 생성되었는지 확인한다.
4. billing receipt나 lifecycle email이 실패한 경우 고객에게 수동 업데이트를 보낸다.

## 8. Production Smoke 실패

명령:

```powershell
scripts/smoke_test_prod.ps1 -Profile full
```

조치:

1. 실패한 check 이름과 URL을 기록한다.
2. `/readyz` config error/warning을 먼저 확인한다.
3. 인증 실패면 smoke test 계정과 token을 확인한다.
4. Stripe 실패면 live/test mode가 섞였는지 확인한다.
5. OAuth 실패면 redirect URI와 app secret을 확인한다.
6. Upload 실패면 storage bucket 권한을 확인한다.

Release 기준:

- full smoke 실패 상태에서는 broad public rollout 금지.
- managed pilot은 실패 범위가 고객 사용 경로 밖이고 수동 운영 대안이 있을 때만 제한적으로 진행한다.
