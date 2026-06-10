# 2026-04-15 Master Commercialization Guide

## 0. 문서 상태

이 문서는 `2026-04-28` 기준으로 다시 작성한 마스터 문서다.

- 기존 파일은 인코딩 손상으로 원문 일부가 실제로 깨져 있었다.
- 이 문서는 손상된 텍스트를 억지로 복원한 문서가 아니라, 현재 코드와 검증 결과를 기준으로 다시 정리한 기준 문서다.
- 앞으로 개발 우선순위, 상용화 판단, 운영 마감 기준은 이 문서를 기준으로 본다.

## 1. 현재 결론

현재 프로젝트는 다음 단계까지는 왔다.

- 제한된 파일럿 상용화: 가능
- 소수 유료 고객 대상 운영: 거의 가능하지만 운영 셋업과 몇 개의 코드 마감이 더 필요
- 공개형 self-serve SaaS: 아직 아님

중요한 판단:

- 지금은 “기능이 없는 프로젝트”가 아니다.
- 반대로 “셋팅만 남은 상태”도 아직 아니다.
- 남은 일은 `운영 셋업`만이 아니라 `코드 측 마감 항목`도 있다.

## 2. 이번 기준 검증 결과

`2026-04-28` 기준 최신 확인 결과:

- backend `pytest -q`: `523 passed, 2 warnings`
- frontend `npm run lint`: `0 errors, 0 warnings`
- frontend `npm run build`: passed

추가 참고:

- 프런트의 `react-hooks/exhaustive-deps` 경고는 현재 기준으로 모두 정리됐다.
- build는 통과하지만 `baseline-browser-mapping` 데이터 갱신 경고는 남아 있다.
- smoke script와 운영 배포 스크립트는 코드상 준비가 많이 되어 있지만, 실제 운영 시크릿/실계정으로 끝까지 돌린 상태는 아니다.

## 2A. 공개 진입면 최신 상태

`2026-04-28` 기준 public-facing 진입면은 예전의 “툴 / SaaS” 중심 문구에서 한 단계 정리됐다.

- 랜딩은 `Get More Calls From Google Maps` 중심의 managed-service 포지션으로 재작성됨
- pricing은 self-serve SaaS 가격표보다 `managed package` 기준 설명으로 재정렬됨
- onboarding은 authenticated 내부 플로우를 유지하면서도 public `free audit` 계약을 실제 백엔드 응답 구조에 맞게 다시 붙였음
- `contact`는 더 이상 가짜 성공 submit가 아니라 실제 `mailto` 초안 오픈 방식으로 바뀜
- `features`는 tool catalog보다 managed monthly work 설명 중심으로 재작성됨
- `demo`는 가짜 영상 플레이어가 아니라 실제 audit -> review call -> monthly work walkthrough로 정리됨
- global metadata / structured data도 `AI automation tool`보다 `managed Google Maps growth service` 쪽으로 정리됨

즉, 공개 유입 경로는 이제 아래 구조에 더 가까워졌다.

- free audit
- audit review contact
- managed pilot 제안
- 내부 dashboard / workspace handoff

## 3. 이미 닫힌 큰 축

이번 시점까지 코드상 크게 닫힌 축은 아래다.

- billing / usage / credits 읽기 경로 정합성 정리
- 다수의 AI usage 차감 시점을 `성공 후 차감` 기준으로 정리
- auth / verification / reset token 저장 하드닝
- OAuth state 보안 하드닝
- dashboard 다수 화면의 demo/mock/fabricated state 제거
- dedicated scheduler worker 실행 경로 추가
- worker/ops 알림 가시성 확대
- dunning 상태 전이와 scheduler payment retry를 inbox/audit 알림 기준으로 정리
- review booster negative review owner alert를 inbox/audit 기준으로 구현
- deprecated `purchase_credits()`를 Stripe checkout wrapper 기준으로 정리
- legacy `call_service`를 active voice-forwarding helper만 남기도록 정리
- external Stripe webhook과 BillingService의 subscription / invoice 처리 경로 단일화
- upload asset 영속 저장, audit, batch preview, migration script 추가
- approval public flow 계약 정리
- report / notification / audit trail 운영형 계약 정리
- admin account suspend / reactivate를 실제 audit-backed operator action으로 구현
- admin monthly credit distribution을 due account 기준의 audit-backed operator action으로 구현
- admin plan changes를 local/Stripe-backed 경로 분리와 audit trail 기준으로 구현
- admin custom usage limit overrides를 account settings 저장 + live usage 반영 기준으로 구현
- legacy `/uploads/post` / `/uploads/post/with-images`를 실제 draft wrapper로 전환
- 프런트 hook dependency warning을 effect-only wrapper 기준으로 정리
- notifications inbox delete를 audit-preserving 방식으로 실제 구현
- 사용되지 않는 legacy `frontend/src/stores/metricsStore.ts` 중복 store 제거

즉, 핵심 제품 골격은 이미 “데모 수준”을 벗어났다.

## 4. 아직 남아 있는 핵심 개발 과제

### 4.1 남은 worker / ops 경로 audit

여전히 운영 기준으로 더 닫아야 하는 항목이 있다.

대표 예시:

- `app/core/usage_limits.py`
  - 일부 사용자 알림 후속 처리 TODO가 남아 있다.
- 그 외 worker / webhook / publish / recovery 예외 경로는 “큰 축”은 닫혔지만 마지막 잔여 audit가 더 필요하다.

`2026-04-28` 이번 턴에는 `admin operations feed`가 실제 운영 알림 타입을 더 많이 집계하도록 보강했다.

- 기존 feed는 일부 worker/service notification만 `worker_ops` 도메인으로 올렸는데, 이번에 아래 운영 알림들도 severity 매핑에 포함했다.
  - `billing_payment_failed`
  - `billing_grace_period_started`
  - `billing_access_restricted`
  - `billing_subscription_suspended`
  - `billing_payment_recovered`
  - `missed_call_text_back_skipped`
  - `missed_call_text_back_failed`
  - `review_booster_negative_review`
- 추가로 `app/core/usage_limits.py`가 생성하는 동적 `usage_warning_*` notification도 이제 prefix 기준으로 `worker_ops` feed에 포함된다.
- 이로써 AI/content 사용량이 월 한도 80% / 90% / 100%에 가까워질 때, inbox 알림뿐 아니라 `/admin` operations feed에서도 같은 위험 신호를 볼 수 있다.
- 또 `app/jobs/metric_jobs.py`는 이제 `GBP data 없음 + carry-forward할 prior snapshot 없음`으로 daily snapshot이 완전히 skip될 때 `daily_snapshot_unavailable` 알림을 남긴다.
- 이 알림은 location별로 주 1회만 발송되도록 throttling되어, 운영자는 analytics baseline이 영원히 비어 있는 상태를 더 빨리 발견할 수 있다.
- 이 보강으로 실제 inbox notification은 생성되지만 `/admin` cross-domain feed에서는 안 보이던 운영 이슈가 줄었다.
- 즉, billing / calls / reviews 쪽 자동화 실패나 위험 상태가 admin 한 화면에서 더 일관되게 보이게 됐다.

의미:

- 큰 줄기의 운영 알림은 많이 닫혔지만, “예외 경로의 마지막 10%”는 아직 남아 있다.
- 이 작업이 끝나야 운영자가 로그 대신 제품 안에서 문제를 수습할 수 있다.

### 4.2 dead control / legacy compatibility 정리

아직 남아 있는 “정직하지 않은” 또는 “운영자가 헷갈릴 수 있는” 경로는 예전보다 많이 줄었다.

`2026-04-28` 이번 턴에는 `admin/disputes`의 남아 있던 dead unavailable 상태도 더 정리했다.

- `/admin/disputes`는 이제 Stripe가 미설정이어도 화면 전체를 막지 않고, persisted local dispute ledger를 그대로 보여준다.
- 이때 응답은 `stripe_available=false`, `data_source=local_cache`, `warning` 메타를 같이 내려서 프런트가 honest banner를 띄우게 했다.
- `Respond` / `Accept` 같은 Stripe write action은 Stripe가 연결될 때까지 disabled 상태로 유지된다.
- 즉, 운영자는 더 이상 “아무것도 안 보이는 disputes 화면” 대신, 최소한 현재 로컬에 남아 있는 dispute footprint와 due date를 계속 볼 수 있다.

의미:

- 큰 501 경로와 deprecated stub은 대부분 정리됐다.
- 공개 진입면의 큰 dead path는 이번에 많이 줄었다.
- 앞으로는 남은 dead control, legacy copy, 운영 예외 경로의 마지막 정리 비중이 더 크다.

### 4.3 upload migration 실제 실행 마감

준비된 것:

- `UploadMigrationService`
- `scripts/migrate_upload_assets.py`
- `/admin/upload-migration-audit`
- `/admin/upload-migration-audit/export`
- `/admin/upload-migration-batch-preview`

아직 남은 것:

- 실제 운영 배치 apply 실행
- 배치 크기 확정
- cleanup manifest 검토
- 로컬 파일 삭제 정책 확정
- migration 후 재검증 절차 확정

현재 마감 문서:

- `docs/UPLOAD_MIGRATION_APPLY_RUNBOOK_KR_2026-04-26.md`

중요:

- 이 항목은 “코드 없음” 문제가 아니라 “실행 전환” 문제다.
- 하지만 아직 실행 전환을 끝내지 않았으므로 완전히 닫힌 상태는 아니다.

### 4.4 운영 화면 마감

남은 화면성 과제는 예전보다 적지만 아직 끝난 건 아니다.

이미 큰 공개 진입면은 정리됐다.

- 랜딩 hero / section / CTA
- managed pricing narrative
- public onboarding flow
- honest contact handoff
- honest features / demo positioning

- 남은 dead control 제거
- read-only 상태를 버튼처럼 보이게 하는 UI 정리
- 공개 화면과 운영 화면의 copy / 상태 문구 일관화

이 영역은 치명도는 낮지만, 상용 제품의 신뢰도에는 직접 영향을 준다.

### 4.5 public launch readiness gate

2026-04-26 기준으로 production readiness 검사가 더 엄격해졌다.

- production에서 `DEBUG=true`, SQLite, localhost/http `APP_URL`, placeholder `JWT_SECRET`는 계속 차단한다.
- Stripe secret/webhook뿐 아니라 public checkout용 subscription price ID 누락도 차단한다.
- production에서 cloud storage, LLM key, GBP OAuth, Instagram OAuth, SendGrid sender가 없으면 launch blocker로 본다.
- dedicated worker는 배포 토폴로지에 따라 API 프로세스와 분리될 수 있으므로, scheduler 미구동은 warning으로 노출한다.
- Sentry / Slack alert 미연결도 warning으로 노출해 live smoke 전에 확인하게 한다.
- 배포 전에는 `python scripts/check_prod_env.py --require-prod`로 같은 기준을 CLI에서 먼저 확인한다.

이 보강으로 “앱은 떴지만 핵심 상용 경로가 실제로는 미연결”인 상태를 더 빨리 발견할 수 있다.

### 4.6 entitlement source of truth 정리 완료

`2026-04-28` 이번 턴에는 `usage entitlement / feature access` 공통 원인을 정리했다.

- 새 helper [app/services/account_entitlements.py](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/app/services/account_entitlements.py) 를 추가해 subscription row가 없는 legacy account의 effective entitlement를 한 군데에서 해석하게 했다.
- `FeatureAccessService`, `CreditsService`, `RateLimiter`, legacy `usage_limits`가 이제 같은 entitlement source를 본다.
- subscription row가 없는 legacy account는 `premium-equivalent feature access + small preview quota` 기준으로 해석된다.
- preview quota는 현재 코드상 다음과 같다.
  - `sms_daily/monthly = 10`
  - `ai_content_daily/monthly = 5`
  - `ai_image_daily/monthly = 3`
  - `ai_response_daily/monthly = 10`
- 이 정리로 이전에 한꺼번에 터졌던 `0/0 daily limit`, `403 feature_not_available`, `200이어야 할 경로가 429/403으로 먼저 막히는 문제`가 공통 축에서 해소됐다.
- 추가로 legacy `app/core/usage_limits.py`는 계정 스코프 집계와 `AI_CONTENT` generated post 집계를 유지하면서 zero-included warning도 남기게 했다.

검증 결과:

- `tests/test_usage_limits_core.py -q`: `7 passed`
- full `pytest -q`: `521 passed, 2 warnings`

## 5. 운영 셋업 과제

아래는 코드보다 운영 준비에 가까운 과제다.

- dedicated worker 실배포
- backend / worker / frontend 환경변수와 시크릿 최종 주입
- Alembic migration 실제 적용
- GCS / SendGrid / Twilio / Stripe / OAuth 실계정 연결
- `scripts/smoke_test_prod.ps1`를 실계정으로 daily/full 실행
- alert webhook 수신 채널 연결
- upload migration 실제 apply 실행

현재 기준으로는 이 과제들도 꽤 크다.
그래서 아직 “셋팅만 남음”이라고 말하면 안 된다.

## 6. 바로 다음 개발 우선순위

앞으로의 기본 순서는 아래로 고정한다.

1. 남은 worker / ops 잔여 경로 audit
2. dead control / legacy copy / deprecated compatibility 경로 정리
3. upload migration apply runbook 마감
4. 프런트 운영 화면 마지막 정리
5. 그 다음에 운영 셋업과 live smoke

즉, `새 기능 추가`보다 `운영형 완성도 마감`이 우선이다.

## 7. “셋팅만 남음”이라고 말할 수 있는 조건

아래가 모두 충족될 때만 그렇게 판단한다.

- 남은 501 / TODO / dead control이 launch blocker가 아니게 정리됨
- worker / ops 예외 경로가 제품 안 알림 기준으로 충분히 닫힘
- usage entitlement / free-tier / feature access 기본값이 full regression 기준으로 안정화됨
- upload migration apply 계획이 아니라 실제 적용 완료 상태가 됨
- Alembic migration 실제 적용 완료
- dedicated worker 실배포 완료
- Stripe / Twilio / OAuth / upload / publish smoke를 실계정으로 통과
- alert / runbook / 회수 절차가 실제 운영 채널과 연결됨

이 기준 전까지는 “개발할 것이 더 남아 있음”으로 본다.

## 8. 앞으로의 개발 원칙

앞으로 이 프로젝트는 아래 원칙으로 계속 개발한다.

- demo/mock/fabricated success는 넣지 않는다.
- 실패하면 정직하게 실패시킨다.
- usage 차감은 성공 후 차감을 기본으로 본다.
- operator가 로그가 아니라 제품 UI 안에서 문제를 볼 수 있어야 한다.
- 새 기능보다 운영형 마감과 source of truth 통일을 우선한다.
- legacy 호환 엔드포인트는 유지하더라도, 정식 경로와 혼동되지 않게 한다.
- 공개 페이지는 “툴 판매”보다 “문제 발견 -> managed 해결 제안” 구조를 우선한다.
- 가짜 submit / fake success / fake structured data는 넣지 않는다.

## 9. 현재 상태 한 줄 요약

이 프로젝트는 이미 파일럿 상용화 가능한 수준까지 왔다.
하지만 아직 `운영형 마감 코드`와 `실운영 셋업`이 모두 남아 있으므로,
현 시점의 정확한 판단은 아래다.

`상용화 직전 단계이지만 아직 셋팅만 남은 상태는 아니다.`
