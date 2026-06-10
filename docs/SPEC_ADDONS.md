# Spec: Add-ons / Billing Boundary

최종 갱신 기준: 현재 코드베이스 / 회귀 테스트 `79 passed`

## 1. 목적
이 문서는 add-on UI 목업이 아니라, 현재 billing/add-on 경계를 설명하는 참고 스펙이다.

## 2. 현재 기준 API 경계
현재 사용자-facing billing 경로는 아래가 핵심이다.
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

참고:
- 과거 문서에 있던 add-on preview/attach/detach 세부 경로는 현재 코드 기준 정본으로 보기 어렵다.
- add-on 개념은 모델/가격표/기능 gating에 존재하지만, 운영 UX는 별도 고도화 대상이다.

## 3. 현재 add-on 모델
현재 코드의 add-on 타입은 아래다.
- `missed_call_text_back`
- `review_booster`
- `website_seo`
- `social_auto_responder`
- `video_generator`

가격 기준:
- `$29`, `$39`, `$49`, `$29`, `$49`

기준 소스:
- `app/models/subscription.py`

## 4. 현재 판단
- 플랜과 가격: 현재 코드 기준 존재
- add-on 개념: 존재
- add-on 운영 UX/API: 문서 수준보다 덜 확정적

## 5. 권장 문서 역할
이 문서는 현재부터는 "확정 API 문서"가 아니라 `billing/add-on 경계 설명서`로 쓰는 것이 맞다.
실제 배포 판단은 아래 문서를 우선 본다.
- [MONETIZATION_BLUEPRINT.md](./MONETIZATION_BLUEPRINT.md)
- [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md)
- [STRIPE_SETUP.md](./STRIPE_SETUP.md)
