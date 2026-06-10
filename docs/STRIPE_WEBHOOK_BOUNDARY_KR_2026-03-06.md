# Stripe Webhook Boundary 정리

작성일: 2026-03-06

## 1. 목적

현재 코드베이스에는 Stripe webhook 관련 진입점이 3개 보입니다.

- `/billing/webhook`
- `/webhooks/stripe`
- `/webhooks/stripe-legacy`

이 문서는 각 경로의 역할, 현재 권장 경로, 향후 정리 방향을 명확히 하기 위한 문서입니다.

## 2. 현재 역할 분리

### A. `/billing/webhook`

파일:
- [billing.py](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/app/routers/billing.py)

현재 역할:
- Stripe signature 존재 여부 검증
- `BillingService.handle_webhook(payload, sig_header)` 위임
- 구독/결제/인보이스 처리의 서비스 레이어 진입점

특징:
- billing 도메인 안에서 처리 흐름이 모여 있음
- idempotency를 라우터 레벨에서 직접 관리하지 않음
- 서비스 구현과 더 강하게 결합되어 있음

### B. `/webhooks/stripe`

파일:
- [webhooks.py](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/app/routers/webhooks.py)
- [stripe_event.py](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/app/models/stripe_event.py)

현재 역할:
- Stripe signature 검증
- `StripeEvent` 기록
- `event_id` unique 기반 idempotency 보장
- 중복 이벤트 무시
- 처리 실패 시에도 event log는 남김

특징:
- 운영 안정성 관점에서 더 안전함
- 중복 배송과 재시도에 강함
- 현재 테스트가 붙어 있는 webhook 경로

### C. `/webhooks/stripe-legacy`

파일:
- [webhooks.py](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/app/routers/webhooks.py)

현재 역할:
- 예전 Stripe webhook 처리 흐름
- 단순 이벤트 분기 처리

상태:
- 더 이상 기본 경로가 아님
- 레거시 호환용으로만 남겨둔 상태

## 3. 현재 권장 경로

운영 기준 primary 경로:
- `/webhooks/stripe`

이유:
- idempotency 보장
- 테스트 존재
- 중복 webhook 배송에 대해 가장 안전함
- 처리 실패 후 재전송 루프를 줄이는 구조로 이미 보강됨

## 4. 현재 문제점

### 문제 1. Stripe webhook 진입점이 중복됨

동일한 Stripe 이벤트를 서로 다른 라우터가 처리할 수 있는 구조는 운영 혼선을 만듭니다.

리스크:
- 어떤 URL을 Stripe Dashboard에 등록해야 하는지 헷갈림
- 개발자가 어느 경로가 정본인지 오해할 수 있음
- 이벤트 처리 방식이 라우터마다 달라질 수 있음

### 문제 2. billing 도메인과 webhook 도메인의 책임이 겹침

`/billing/webhook`도 Stripe 이벤트를 처리하고, `/webhooks/stripe`도 Stripe 이벤트를 처리합니다.

즉:
- billing 서비스 중심 처리
- webhook 로그 중심 처리

두 철학이 섞여 있습니다.

### 문제 3. `/webhooks/stripe-legacy`가 살아 있어 읽는 사람을 혼란시킴

현재는 경로 이름으로는 legacy임을 표시했지만, 코드베이스에 남아 있는 한 유지보수자가 다시 건드릴 가능성이 있습니다.

## 5. 권장 운영 방침

### 즉시 방침

- Stripe Dashboard webhook endpoint는 `/webhooks/stripe`만 사용
- `/billing/webhook`는 외부 Stripe endpoint로 등록하지 않음
- `/webhooks/stripe-legacy`는 신규 연동 금지

### 코드 해석 기준

- Stripe 외부 수신 정본: `/webhooks/stripe`
- Billing domain 내부 처리 로직: `BillingService`
- 레거시 비교/참고 코드: `/webhooks/stripe-legacy`

## 6. 권장 리팩터링 방향

### 옵션 A. `/webhooks/stripe`를 정본으로 유지

가장 현실적인 방향입니다.

구조:
1. `/webhooks/stripe`에서 signature 검증
2. `StripeEvent` 기록 및 idempotency 처리
3. 이후 실제 비즈니스 처리는 `BillingService` 또는 전용 dispatcher에 위임

장점:
- 현재 테스트 자산 유지 가능
- 중복 방어 구조 유지
- webhook 진입점이 명확해짐

### 옵션 B. `/billing/webhook`를 정본으로 올리고 idempotency 흡수

가능은 하지만 지금 시점에서는 비추천입니다.

이유:
- 이미 `/webhooks/stripe`에 안정성 패치와 테스트가 붙어 있음
- 굳이 다시 billing 라우터로 옮길 이유가 약함

## 7. 추천 결정

현재 코드베이스 기준 추천:

1. `/webhooks/stripe`를 정식 Stripe webhook endpoint로 고정
2. `/billing/webhook`는 내부 호환용 또는 점진적 제거 대상으로 표시
3. `/webhooks/stripe-legacy`는 추후 삭제
4. webhook 비즈니스 처리 코드는 장기적으로 `BillingService`로 수렴

## 8. 다음 액션

### P0

- README 또는 배포 문서에 Stripe endpoint를 `/webhooks/stripe`로 명시
- Stripe Dashboard 설정값도 동일하게 맞춤

### P1

- `/billing/webhook`에 deprecated 주석 추가
- `/webhooks/stripe-legacy` 삭제 가능성 평가

### P2

- `/webhooks/stripe` 내부 분기 처리를 `BillingService` 또는 dispatcher로 정리
- webhook event replay/runbook 문서 추가

## 9. 결론

현재 운영 기준으로 Stripe webhook 정본은 `/webhooks/stripe`입니다.

`/billing/webhook`는 살아 있지만 정본으로 보기 어렵고, `/webhooks/stripe-legacy`는 이름 그대로 레거시입니다.

즉, 앞으로의 기준은 아래 한 줄로 정리하면 됩니다.

> Stripe는 `/webhooks/stripe`로 받고, idempotency는 여기서 보장한다.
