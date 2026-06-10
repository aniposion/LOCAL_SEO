# 상용화 개선 진행 현황

작성일: `2026-05-02`

## 1. 이번 개발에서 완료한 개선

### 1.1 문의/파일럿 리드 유실 방지

- 공개 contact form이 더 이상 `mailto:`에만 의존하지 않음
- `POST /contact/requests`로 문의를 DB에 저장
- `GET /contact/requests`, `PATCH /contact/requests/{id}`로 admin 조회와 상태 변경 지원
- admin inbox notification 생성
- admin 화면에 Contact Requests 섹션 추가
- 상태: `new`, `contacted`, `closed`, `spam`
- 같은 이메일/source의 5분 내 중복 제출은 `429`로 차단

### 1.2 관리형 파일럿 가격 메시지 정합성

- 무료 감사/솔루션 흐름에서 내부 SaaS 플랜명(`starter`, `pro`)이 새지 않도록 보정
- 공개 판매 패키지 기준으로 추천 패키지 반환
  - `maps_starter`: Maps Starter, `$699/mo`, `$499 setup`
  - `calls_growth`: Calls Growth, `$999/mo`, `$799 setup`
  - `competitive_market`: Competitive Market, `$1,499/mo`, `$1,500 setup`
- 온보딩 솔루션 화면에 Recommended Managed Pilot 카드 추가

### 1.3 API public path 혼선 완화

- 루트 경로는 계속 canonical로 유지
- `/api/v1` alias를 앱 자체에서 지원
- 예:
  - `/contact/requests`
  - `/api/v1/contact/requests`
  - `/webhooks/stripe`
  - `/api/v1/webhooks/stripe`
- `/api/v1/healthz`, `/api/v1/readyz`도 지원

### 1.4 검증

- `pytest tests/test_health.py tests/test_locations.py tests/test_posts.py tests/test_roi_service.py tests/test_approval_service.py tests/test_billing_integration.py tests/test_p0_webhook_idempotency.py tests/test_metrics_content_social.py tests/test_review_responder.py tests/test_review_booster.py tests/test_calls.py tests/test_jobs.py tests/test_api_prefix.py tests/test_contact_requests.py tests/test_conversion_pricing.py -q`: `198 passed`
- `pytest tests/test_api_prefix.py tests/test_contact_requests.py tests/test_conversion_pricing.py tests/test_health.py -q`: `13 passed`
- `pytest tests/test_contact_requests.py tests/test_conversion_pricing.py -q`: `7 passed`
- `frontend npm run lint`: 통과
- `frontend npm run build`: 통과
- `python -c "import app.main; print('ok')"`: 통과

## 2. 현재 판매 가능 판단

현재는 `유료 파일럿 판매 가능`에 더 가까워졌다.

권장 판매 방식:

- 홈서비스 등 고가 전화 리드 업종
- 5~10개 업체 제한
- 월 `$699~$999` 중심
- 3개월 파일럿
- founder-led onboarding / support / recovery

아직 broad public self-serve SaaS로 열기에는 이르다.

## 3. 아직 남은 개선 항목

### P0. 운영 환경 smoke test

- 실제 staging/production URL 기준 smoke test
- Stripe webhook public URL 확인
- Twilio voice/SMS callback 확인
- Google OAuth callback 확인
- `NEXT_PUBLIC_API_URL`이 루트 또는 `/api/v1` 중 어떤 기준을 쓰는지 배포 환경에서 고정

### P0. DB migration 적용

- 새 migration: `20260502_contact_requests`
- 배포 전 `alembic upgrade head` 필요

### P1. 결제/상품 운영 정책 정리

- 공개 관리는 `$699+` 패키지
- 내부 SaaS billing은 `$99/$149/$249/$499`
- 당장은 managed pilot은 sales-assisted로 팔고, self-serve checkout은 별도 단계로 분리하는 것이 안전

### P1. 리드 후속 전환 루프

- Contact Request에서 audit id 또는 source campaign 연결
- contacted/closed 시 전환 사유 기록
- won/lost 상태 추가 여부 검토
- admin conversion analytics에 contact request funnel 반영

### P1. 이메일 전달성

- contact request 생성 시 admin inbox는 남지만, 외부 이메일 발송은 운영 설정에 의존
- SendGrid 또는 SMTP production 설정 확인 필요

### P1. 외부 연동 운영 검증

- Google Business Profile publishing
- Instagram/Facebook OAuth 갱신
- Twilio missed-call text back
- uploads/storage failure recovery

## 4. 다음 개발 순서 제안

1. staging에서 migration + smoke test 실행
2. Contact Request를 conversion analytics에 연결
3. managed pilot 전용 계약/결제 운영 플로우 정리
4. OAuth/Twilio/Stripe 실제 계정 기반 end-to-end 테스트
5. 운영자 runbook과 failed-payment/retry 화면 마감
