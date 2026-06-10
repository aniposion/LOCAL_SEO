# Product Readiness 체크리스트

작성일: 2026-05-18  
판정: managed pilot 제한 판매 가능, broad self-serve 판매 보류.

## P0 완료 기준

- [ ] staging/prod secret 주입 완료
  - Stripe live secret/webhook
  - `STRIPE_PRICE_MAPS_STARTER_MONTHLY`
  - `STRIPE_PRICE_MAPS_STARTER_YEARLY`
  - `STRIPE_PRICE_CALLS_GROWTH_MONTHLY`
  - `STRIPE_PRICE_CALLS_GROWTH_YEARLY`
  - `STRIPE_PRICE_COMPETITIVE_MARKET_MONTHLY`
  - `STRIPE_PRICE_COMPETITIVE_MARKET_YEARLY`
  - cloud storage
  - GBP OAuth
  - Instagram OAuth
  - JWT secret
  - SendGrid sender
- [ ] `python scripts/check_prod_env.py --require-prod` 통과
- [ ] `alembic upgrade head` staging/prod 통과
- [ ] `scripts/smoke_test_prod.ps1 -Profile full` 통과
- [x] 공개 managed pilot 가격과 `/billing/plans` 기본 catalog 정렬
- [x] legacy self-serve catalog를 `/billing/plans?catalog=legacy`로 보존
- [x] README 한글 인코딩 복구
- [x] dirty worktree 정리 원칙 문서화

## P1 완료 기준

- [x] contact funnel 상태 확장: `booked`, `won`, `lost`
- [x] contact request에 `audit_id`, `close_reason`, funnel timestamp 추가
- [x] admin sales summary API 추가
- [x] admin dashboard에 booked/won conversion, response SLA, stale lead 표시
- [x] onboarding 실패 시 retry/contact next action 표시
- [x] OAuth callback 실패 시 retry/contact next action 표시
- [x] checkout cancel/success 후 billing next action 표시
- [x] billing/support/incident runbook 추가

## P2 운영 기준

- [ ] 파일럿 고객 5-10개 운영
- [ ] 고객별 blocker 태그 기록
- [ ] support time/customer/month 기록
- [ ] gross margin 추적
- [ ] AI cost 추적
- [ ] Twilio/SMS cost 추적
- [ ] managed-only 기능과 self-serve 후보 분리

## Sales Funnel 운영 상태

권장 상태 전이:

1. `new`: inbound lead 생성.
2. `contacted`: 첫 이메일/전화 발송.
3. `booked`: discovery 또는 audit review 미팅 예약.
4. `won`: pilot 결제/계약 완료.
5. `lost`: 구매하지 않음. `close_reason` 필수로 남긴다.
6. `closed`: 기타 종료.
7. `spam`: 운영 지표에서 제외할 수 있는 불량 lead.

## Release 전 최종 확인

```bash
python -c "import app.main; app.main.app.openapi(); print('openapi ok')"
pytest -q
cd frontend
npm run lint
npm run build
```

운영 환경:

```bash
python scripts/check_prod_env.py --require-prod
alembic upgrade head
scripts/smoke_test_prod.ps1 -Profile full
```
