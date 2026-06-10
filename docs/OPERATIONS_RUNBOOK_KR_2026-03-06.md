# 운영 Runbook

작성일: 2026-03-06
최종 갱신 기준: `2026-04-01`

## 1. 목적

이 문서는 현재 운영 기준에서 가장 민감한 세 영역의 대응 절차를 정리한다.

1. billing / subscription
2. Stripe webhook
3. review booster delivery failure

이 문서는 broad public self-serve 운영용 완결 runbook이 아니라, `limited pilot`와 `소수 고객 베타 운영` 기준의 실무 문서다.

## 2. 공통 원칙

- 먼저 증상보다 `영향 범위`를 파악한다.
- 데이터 정합성을 깨는 수동 조치는 마지막에 한다.
- Stripe / Twilio 외부 상태와 내부 DB 상태를 같이 본다.
- 복구 후에는 재발 방지 메모를 남긴다.
- public API path가 루트 기준인지 `/api/v1` rewrite 기준인지 먼저 확인한다.

## 3. Billing / Subscription Runbook

### 3.1 대표 증상

- 결제가 성공했는데 구독 상태가 안 바뀐다
- billing page에서 subscription이 비정상으로 보인다
- usage / feature gating이 실제 결제 상태와 다르게 보인다
- invoice / payment history가 비어 있거나 늦게 반영된다

### 3.2 1차 확인

1. 사용자의 `subscription` 레코드 확인
2. 최근 Stripe webhook 수신 여부 확인
3. Stripe Dashboard의 실제 subscription / invoice / payment 상태 확인
4. `stripe_events` 중복 처리나 실패 흔적 확인

### 3.3 확인 포인트

- `subscriptions.status`
- `subscriptions.plan_type`
- `subscriptions.stripe_subscription_id`
- 최근 `invoice.payment_failed`, `invoice.payment_succeeded`, `customer.subscription.updated` 이벤트
- feature gating이 subscription 상태와 일치하는지

### 3.4 조치 순서

1. Stripe Dashboard 기준 상태를 정본으로 본다
2. Stripe가 실제로 어떤 public webhook path로 이벤트를 보내는지 확인한다
3. 같은 `event_id`가 이미 처리됐는지 `stripe_events`에서 확인한다
4. 내부 subscription 상태가 늦게 반영된 경우 webhook 처리 로그를 점검한다
5. 수동 수정이 필요하면 DB 직접 수정 전에 원인과 재발 여부를 먼저 확인한다

### 3.5 금지 사항

- 원인 확인 없이 subscription status를 임의로 바꾸지 않는다
- legacy `/billing/webhook`를 새 정본처럼 취급하지 않는다

## 4. Stripe Webhook Runbook

### 4.1 정본 경로

- backend app route: `/webhooks/stripe`
- legacy compatibility route: `/billing/webhook`
- deprecated route: `/webhooks/stripe-legacy`

주의:

- `/api/v1/webhooks/stripe`는 앱 내부 기본 path가 아니다
- ingress / proxy가 `/api/v1 -> /`를 명시적으로 rewrite하는 경우에만 public path로 사용한다

### 4.2 대표 증상

- Stripe Dashboard에서는 delivered인데 앱 상태가 안 바뀜
- 같은 이벤트가 여러 번 와서 중복 반영되는 것 같음
- webhook 4xx / 5xx 증가

### 4.3 1차 확인

1. Stripe Dashboard webhook delivery log 확인
2. backend 로그에서 chosen public path 처리 결과 확인
3. `stripe_events`에 해당 `event_id`가 저장됐는지 확인
4. duplicate가 예상대로 무시됐는지 확인

### 4.4 정상 기대 동작

- signature 검증 통과
- `event_id`가 한 번만 기록됨
- duplicate delivery는 side effect 없이 무시됨
- 처리 실패 이벤트도 감사용 기록은 남음

### 4.5 장애 대응

#### case A. signature 오류

- webhook secret 불일치 여부 확인
- environment 변수 재검증
- Stripe Dashboard endpoint secret 교차 확인

#### case B. duplicate side effect 의심

- `stripe_events`에 중복 row가 생겼는지 먼저 확인
- 동일 `event_id`가 여러 번 처리됐는지 로그 확인
- `/webhooks/stripe` 외 다른 경로로 들어간 이벤트가 없는지 확인

#### case C. legacy 경로 유입

- `/billing/webhook` 또는 `/webhooks/stripe-legacy` hit 여부 확인
- 새 설정은 무조건 chosen public Stripe path로 통일

## 5. Review Booster Runbook

### 5.1 현재 기능 상태

- request send 흐름 존재
- retry 정책 존재
- manual requeue 존재
- terminal failure operator notification 존재

### 5.2 대표 증상

- request가 `FAILED`로 멈춤
- retry가 반복되다가 더 이상 진행되지 않음
- 고객에게 SMS / Email이 실제로 안 감
- 운영자 알림이 왔는데 어떤 조치를 해야 할지 모름

### 5.3 현재 retry 정책

- 1차 실패: 5분 후 재시도
- 2차 실패: 30분 후 재시도
- 3차 실패: 종료
- 종료 시 운영자 알림 전송

### 5.4 확인 포인트

- `status`
- `retry_count`
- `last_attempt_at`
- `next_retry_at`
- `last_error`
- `channel`
- 수신자 email / phone 값 유효성

### 5.5 운영 절차

#### case A. 아직 자동 재시도 예정

- `status = FAILED`
- `retry_count < 3`
- `next_retry_at` 존재

조치:

1. 즉시 수동 개입하지 않는다
2. `last_error`를 확인한다
3. 채널 설정이나 수신자 데이터가 명백히 잘못됐는지만 확인한다
4. 예정 시각 이후 자동 재시도 결과를 확인한다

#### case B. terminal failure

- `status = FAILED`
- `retry_count >= 3`
- `next_retry_at = null`

조치:

1. 운영자 알림 내용을 확인한다
2. `last_error`가 데이터 문제인지 외부 채널 문제인지 구분한다
3. 데이터 오류면 phone / email / consent 상태를 수정한다
4. 원인 제거 후 manual requeue를 수행한다

#### case C. 수동 재큐

현재 기준 수동 재큐 경로:

- `POST /review-booster/requests/{request_id}/requeue`

재큐 시 기대 상태:

- `status -> pending`
- `retry_count -> 0`
- `next_retry_at -> null`
- `last_error -> null`
- `last_attempt_at -> null`

### 5.6 금지 사항

- 원인 확인 없이 반복 재큐하지 않는다
- consent / 수신 채널 문제가 있는 request를 그대로 재큐하지 않는다

## 6. 운영 체크

배포 후 최소 확인:

1. Stripe webhook delivery 정상 수신
2. billing page와 실제 Stripe 상태 일치
3. review booster 실패 건이 operator notification으로 보이는지
4. manual requeue 후 상태가 `pending -> sent / delivered`로 정상 이동하는지

## 7. 참고 문서

- [DEPLOYMENT_CHECKLIST.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/DEPLOYMENT_CHECKLIST.md)
- [STRIPE_SETUP.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/STRIPE_SETUP.md)
- [STRIPE_WEBHOOK_BOUNDARY_KR_2026-03-06.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/STRIPE_WEBHOOK_BOUNDARY_KR_2026-03-06.md)
- [MONETIZATION_BLUEPRINT.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/MONETIZATION_BLUEPRINT.md)
- [CODE_IMPROVEMENT_CHECKLIST_KR_2026-03-06.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/CODE_IMPROVEMENT_CHECKLIST_KR_2026-03-06.md)

## 8. 결론

현재 운영에서 가장 중요한 것은 `장애가 안 나는 것`보다 `장애가 났을 때 어디를 보고 어떻게 복구할지 아는 것`이다.
이 runbook은 지금 제품 단계에서 가장 빈도 높고 영향 큰 세 축을 우선 정리한 버전이다.
