# Monetization Blueprint

최종 갱신 기준: 현재 코드베이스 / 회귀 테스트 `79 passed`

## 1. 목적
이 문서는 현재 제품의 monetization 구조를 `실제 코드 기준`으로 정리한 문서다.
예전처럼 "몇 주 안에 전부 완료"라는 실행 기록이 아니라, 현재 과금 구조와 남은 monetization 과제를 보는 기준 문서로 읽어야 한다.

## 2. 현재 과금 구조

### 2.1 플랜
현재 코드 기준 플랜은 아래와 같다.
- `free`
- `starter` = `$99/mo`
- `pro` = `$149/mo`
- `premium` = `$249/mo`
- `agency` = `$499/mo`
- `enterprise` = legacy compatibility enum

기준 소스:
- `app/models/subscription.py`
- `app/routers/billing.py`

### 2.2 add-on 구조
현재 코드 기준 add-on 개념은 아래와 같다.
- `missed_call_text_back`
- `review_booster`
- `website_seo`
- `social_auto_responder`
- `video_generator`

가격 기준:
- `missed_call_text_back` = `$29`
- `review_booster` = `$39`
- `website_seo` = `$49`
- `social_auto_responder` = `$29`
- `video_generator` = `$49`

기준 소스:
- `app/models/subscription.py`

## 3. 현재 billing 경계

### 3.1 사용자-facing billing API
현재 핵심 billing 경로는 아래다.
- `GET /billing/plans`
- `GET /billing/plans/{plan_id}`
- `GET /billing/subscription`
- `POST /billing/checkout`
- `POST /billing/portal`
- `POST /billing/cancel`
- `POST /billing/reactivate`
- `GET /billing/usage`
- `GET /billing/payment-history`
- `GET /billing/invoices`

### 3.2 Stripe webhook 경계
- 정식 Stripe 외부 수신 endpoint: `/api/v1/webhooks/stripe`
- legacy compatibility route: `/api/v1/billing/webhook`
- `/webhooks/stripe-legacy`: hidden + `410 Gone`

즉, monetization 문서에서 가장 먼저 맞춰야 하는 기준은 `billing router`와 `Stripe webhook 정본 분리`다.

## 4. usage 구조
현재 코드상 usage는 두 층으로 나뉜다.

### 4.1 subscription / feature access 관점
- 플랜별 feature 포함 여부
- 플랜별 locations/posts 한도
- 일부 기능은 premium 포함 또는 add-on으로 분리

기준 소스:
- `PLAN_FEATURES` in `app/models/subscription.py`

### 4.2 usage / credits 관점
- `/usage/*` 라우터 존재
- `UsageLimiterService` 기반 usage summary/limit/check 흐름 존재
- credits 관련 경로는 아직 demo/mock 성격이 일부 남아 있음

판단:
- subscription billing은 핵심 흐름이 존재한다.
- usage/credits는 구조는 있으나 운영 현실과 1:1로 고정된 상태는 아니다.

## 5. 현재 monetization에서 실제로 강해진 부분
- Stripe webhook idempotency 보강
- billing integration 테스트 포함
- 문서상 정식 Stripe endpoint 통일
- review booster, calls, ROI 같은 유료 기능 흐름이 실제 제품 가치와 연결됨
- 플랜/enum/가격 정합성 오류 상당수 정리

## 6. 아직 남은 monetization 과제
1. billing / usage / credits의 장기 단일 소스 정리
2. add-on attach/detach와 실제 운영 UX 정교화
3. subscription 상태 전이와 feature gating의 end-to-end 운영 검증
4. dunning / recovery / operator visibility 강화
5. 실매출 기반 ROI와 과금 설득 포인트 연결 강화

## 7. 현재 판단
이 제품은 더 이상 "과금 불가" 상태로 보는 것은 맞지 않는다.
다만 아래처럼 보는 것이 정확하다.

- Stripe billing 핵심 흐름: 사용 가능
- usage/credits 체계: 부분 완료
- monetization UX: 부분 완료
- broad self-serve charging: 운영 검증이 더 필요

## 8. 같이 봐야 하는 문서
- [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md)
- [STRIPE_SETUP.md](./STRIPE_SETUP.md)
- [DEPLOYMENT_RISK_ASSESSMENT_KR_2026-03-06.md](./DEPLOYMENT_RISK_ASSESSMENT_KR_2026-03-06.md)
- [FEATURE_MATRIX.md](./FEATURE_MATRIX.md)

## 9. 결론
현재 monetization 구조는 `가격표만 있는 상태`가 아니라 실제 billing 흐름이 있는 상태다.
하지만 usage/credits와 운영 복구 체계까지 완전히 마감된 것은 아니므로, 현재 단계는 `제한적 파일럿 기준 과금 가능, 일반 대규모 공개 과금은 보수적 접근`이 맞다.
