# Product 판매 가능성 개선 설계서

작성일: 2026-05-18  
목표: Local SEO Optimizer를 유료 managed pilot으로 판매 가능한 상태까지 끌어올리고, self-serve 확장은 검증된 운영 지표 이후로 분리한다.

## 1. 제품 판정

현재 제품은 제한된 managed pilot 판매는 가능하지만, 완전한 self-serve SaaS로 공개 판매하기에는 아직 부족하다.

- 판매 가능 범위: founder-led sales, 5-10개 파일럿 고객, 3개월 managed pilot.
- 판매 보류 범위: 카드만 넣고 즉시 확장되는 broad self-serve, 무인 온보딩, 무인 장애 대응.
- 핵심 이유: 공개 가격, Stripe 상품, 운영 퍼널, 실패 UX, production runbook이 같은 판매 motion을 바라보도록 아직 완전히 정렬되어 있지 않다.

## 2. 목표 판매 motion

1. 방문자는 무료 audit 또는 contact funnel로 들어온다.
2. 제품은 lead score와 추천 managed package를 생성한다.
3. 운영자는 admin sales dashboard에서 SLA, 전환율, 상태를 관리한다.
4. 결제는 공개 managed pilot 패키지와 동일한 Stripe price id로 생성된다.
5. 온보딩, OAuth, 결제 실패 시 고객에게 다음 행동이 명확히 제공된다.
6. 5-10개 파일럿 운영 후 support load, gross margin, AI/Twilio 비용을 근거로 self-serve 범위를 결정한다.

## 3. P0 설계

### P0-1. staging/prod 환경변수 완성

범위:
- Stripe: 공개 managed pilot 패키지 price id, webhook secret, portal config.
- Storage: production bucket/provider, upload limits.
- GBP: OAuth client, redirect uri, scopes.
- Instagram: OAuth client, redirect uri, scopes.
- JWT: placeholder가 아닌 production secret.
- Email: transactional sender, admin recipients, provider key.

구현:
- `app/core/config.py`에 managed pilot Stripe price id를 명시한다.
- `app/core/production_readiness.py`와 `scripts/check_prod_env.py`가 legacy SaaS 가격 대신 managed pilot 가격 누락을 경고한다.
- `.env.example`은 staging/prod에 필요한 key를 사람이 채울 수 있게 최신화한다.

합격 기준:
- `python scripts/check_prod_env.py`에서 P0 blocking error가 없다.
- placeholder JWT, 누락된 managed Stripe price id, storage/OAuth/email 누락은 warning/error로 명확히 노출된다.

### P0-2. migration + prod smoke

명령:
- `alembic upgrade head`
- `scripts/smoke_test_prod.ps1 -Profile full`

로컬 한계:
- 실제 staging/prod secret과 DB가 필요하므로 Codex 로컬에서 완료 처리하지 않는다.
- 대신 migration head가 하나인지, 테스트 DB에서 migration과 앱 import가 깨지지 않는지 검증한다.

합격 기준:
- Alembic head가 단일 head다.
- smoke test가 `/health`, `/ready`, auth, contact funnel, billing checkout, OAuth callback failure path를 확인한다.

### P0-3. 공개 가격과 실제 billing 상품 통일

공개 상품:
- `maps_starter`: Maps Starter, $699/mo, managed 3-month pilot.
- `calls_growth`: Calls Growth, $999/mo, managed 3-month pilot.
- `competitive_market`: Competitive Market, $1499/mo, managed 3-month pilot.

구현:
- `PlanType`에 위 세 상품을 1급 plan으로 추가한다.
- `/billing/plans` 기본 응답은 공개 managed pilot 상품을 반환한다.
- legacy `starter/pro/premium/agency`는 내부 호환 및 기존 고객용 catalog로 남긴다.
- Stripe checkout은 managed plan id와 managed price id를 그대로 사용한다.

합격 기준:
- pricing page, billing API, Stripe checkout metadata가 같은 package id를 사용한다.
- billing dashboard가 공개 managed package를 기본 상품으로 보여준다.

### P0-4. README/제품 문서 인코딩 복구

구현:
- 깨진 한글 문서는 새 UTF-8 문서로 교체하거나 최신 문서로 재작성한다.
- README는 현재 제품 사용법, 환경변수, 검증 명령, 운영 제한을 짧고 정확하게 안내한다.

합격 기준:
- README와 제품 readiness 문서가 정상 한글로 렌더링된다.
- 문서가 실제 명령과 가격 구조를 반영한다.

### P0-5. release branch 기준 dirty worktree 정리

원칙:
- 기존 변경은 사용자 또는 이전 작업 산출물로 간주하고 임의로 되돌리지 않는다.
- 이번 개선의 변경 파일을 분리해 검토 가능한 단위로 남긴다.
- destructive cleanup은 별도 승인 후 수행한다.

합격 기준:
- 이번 변경 파일 목록이 명확하다.
- release branch에서는 untracked/generated 파일 처리 방침이 문서화되어 있다.

## 4. P1 설계

### P1-1. contact lead funnel 확장

상태:
- `new`
- `contacted`
- `booked`
- `won`
- `lost`
- `closed`
- `spam`

필드:
- `audit_id`: 무료 audit 또는 onboarding audit과 연결.
- `close_reason`: lost/closed 사유.
- `booked_at`, `won_at`, `lost_at`: funnel timestamp.

합격 기준:
- admin이 lead를 booked/won/lost로 바꿀 수 있다.
- close reason과 audit id가 API 응답에 포함된다.
- 상태 변경 시 timestamp가 자동 기록된다.

### P1-2. admin sales dashboard

지표:
- 총 lead 수.
- new/contacted/booked/won/lost/spam 수.
- booked conversion rate.
- won conversion rate.
- 평균 첫 응답 시간.
- 24시간 이상 미응답 lead 수.

합격 기준:
- admin page에서 전환율과 SLA를 한눈에 본다.
- `/contact/summary` API가 계산 값을 반환한다.

### P1-3. billing/support/incident runbook

문서:
- 결제 실패, 환불/취소, webhook 지연, OAuth 실패, GBP/Instagram 장애, email 장애.
- 고객 안내 문구와 내부 복구 절차.

합격 기준:
- 운영자가 고객 문의를 받았을 때 첫 응답, 확인 명령, escalation 기준을 바로 찾을 수 있다.

### P1-4. 실패 UX 보강

실패 범위:
- onboarding 생성/분석 실패.
- GBP/Instagram OAuth 실패.
- checkout/payment 실패.

합격 기준:
- 화면에 다음 행동이 보인다: 다시 시도, contact sales, billing support, 상태 확인.
- 오류가 toast로만 사라지지 않는다.

## 5. P2 설계

### P2-1. 파일럿 반복 이슈 수집

운영:
- 5-10개 고객을 동일한 managed pilot funnel로 운영한다.
- 각 고객마다 onboarding blocker, OAuth blocker, content approval blocker, billing issue를 태깅한다.

### P2-2. support load, gross margin, AI/Twilio 비용 추적

지표:
- 고객당 월 support 시간.
- 고객당 gross margin.
- AI cost, SMS/Twilio cost, storage cost.
- 사람이 대신 처리한 managed work 시간.

### P2-3. self-serve vs managed-only 분리

self-serve 후보:
- audit 생성.
- dashboard 조회.
- review response draft.
- billing portal.

managed-only 유지 후보:
- GBP/Instagram 연결 복구.
- competitor strategy.
- 고위험 자동 게시.
- 고객별 campaign setup.

## 6. 개발 순서

1. 이 설계서를 기준 문서로 추가한다.
2. P0 가격/Stripe/env readiness를 코드에 반영한다.
3. P1 contact funnel과 admin dashboard를 확장한다.
4. 실패 UX와 runbook을 보강한다.
5. migration, unit/API tests, frontend lint/build를 실행한다.
6. 외부 secret/staging/prod smoke 잔여 작업을 체크리스트로 남긴다.

## 7. 완료 정의

로컬에서 완료 가능한 항목:
- managed pilot plan이 backend/frontend/test에 반영된다.
- contact funnel과 dashboard summary가 동작한다.
- README와 runbook이 정상 UTF-8로 읽힌다.
- 테스트와 빌드가 통과한다.

외부 의존 항목:
- 실제 Stripe live price id 생성.
- staging/prod secret 주입.
- production DB migration.
- full prod smoke 실행.
- release branch cleanup 승인.
