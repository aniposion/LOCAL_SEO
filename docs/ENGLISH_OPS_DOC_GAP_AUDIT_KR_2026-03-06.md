# English Ops Document Gap Audit

작성일: 2026-03-06
최종 갱신 기준: 현재 코드베이스 / 회귀 테스트 `79 passed`
대상 문서:
- `docs/DEPLOYMENT_CHECKLIST.md`
- `docs/STRIPE_SETUP.md`
- `DEPLOYMENT_GUIDE.md`
- `DEPLOY_GCP.md`

## 1. 목적
오래된 영문 운영 문서와 현재 코드 기준의 차이를 정리한다.
문서별로 다음 셋 중 어디에 해당하는지 판단하는 것이 목적이다.

1. 그대로 써도 되는 문서
2. 최신 상태가 반영됐지만 주기적으로 다시 확인해야 하는 문서
3. 참고용으로만 봐야 하는 문서

## 2. 현재 기준 운영 사실
영문 운영 문서가 따라야 하는 현재 기준은 아래와 같다.

- 회귀 테스트 기준: `79 passed`
- 배포 가능 범위: `staging`, `internal demo`, `limited pilot`
- 정식 Stripe endpoint: `/api/v1/webhooks/stripe`
- `/webhooks/stripe-legacy`: hidden + `410 Gone`
- review booster는 자동 재시도, terminal failure 운영자 알림, manual requeue가 반영됨
- calls는 dashboard API뿐 아니라 Twilio SMS/voice webhook 테스트까지 포함됨
- Stripe webhook idempotency는 `/webhooks/stripe` 기준으로 테스트됨

## 3. 문서별 평가

### 3.1 `docs/DEPLOYMENT_CHECKLIST.md`
현재 상태:
- 최신 상태 반영됨
- 회귀 테스트 수치와 배포 게이트가 현재 코드 기준과 일치함

현재 문서가 반영하는 내용:
- `79 passed`
- uploads, approval, ownership, Twilio, Stripe smoke test
- 제한적 파일럿 기준 배포 판단

판단:
- 현재 운영 판단의 정본으로 사용 가능

### 3.2 `docs/STRIPE_SETUP.md`
현재 상태:
- 최신 상태 반영됨

현재 문서가 반영하는 내용:
- canonical endpoint는 `/api/v1/webhooks/stripe`
- Stripe CLI forwarding 경로 정리
- webhook idempotency 운영 체크 포함
- legacy route와 정식 route 역할 분리

판단:
- Stripe 운영 설정 문서로 그대로 사용 가능

### 3.3 `DEPLOYMENT_GUIDE.md`
현재 상태:
- 재작성 완료
- 현재 배포 전략과 일치함

현재 문서가 반영하는 내용:
- public production이 아니라 controlled rollout 기준
- `79 passed` 기준 회귀 확인
- approval, uploads, Twilio, Stripe, billing 운영 체크

판단:
- 환경 구축과 배포 흐름 설명용 정식 문서로 사용 가능

### 3.4 `DEPLOY_GCP.md`
현재 상태:
- 재작성 완료
- GCP 기준 실제 배포 문서로 사용 가능

현재 문서가 반영하는 내용:
- Cloud Run + Cloud SQL + Secret Manager + Artifact Registry + GCS
- `/api/v1/webhooks/stripe` 정식 endpoint 반영
- pilot rollout 기준과 smoke test 반영

판단:
- GCP 배포 문서로 사용 가능

## 4. 남아 있는 문서 갭
영문 운영 문서 자체는 많이 정리됐지만, 아래는 계속 관리해야 한다.

1. 회귀 테스트 수치 갱신
- 테스트 수치가 바뀌면 `DEPLOYMENT_CHECKLIST.md`, `DEPLOYMENT_GUIDE.md`, `DEPLOY_GCP.md`를 같이 올려야 한다.

2. Stripe legacy 완전 삭제 시점 반영
- 지금은 `/webhooks/stripe-legacy`가 hidden + `410 Gone` 상태다.
- 운영 access log 기준 미사용이 확인되면 문서도 `완전 삭제` 기준으로 다시 바꿔야 한다.

3. review booster 운영 절차 보강
- terminal failure 발생 시 운영자가 무엇을 보고, 어떻게 manual requeue 하는지 runbook 수준의 절차 문서가 더 있으면 좋다.

## 5. 권장 읽기 순서
영문 운영 문서를 읽는 순서는 아래가 가장 낫다.

1. `docs/DEPLOYMENT_CHECKLIST.md`
2. `DEPLOYMENT_GUIDE.md`
3. `DEPLOY_GCP.md`
4. `docs/STRIPE_SETUP.md`

이 순서가 맞는 이유:
- 먼저 배포 gate를 확인하고
- 그 다음 일반 배포 가이드를 보고
- GCP 환경 세부 구성을 맞춘 뒤
- 마지막에 Stripe 세부 설정을 보는 흐름이기 때문이다.

## 6. 결론
영문 운영 문서는 예전처럼 깨진 문자열과 오래된 가정 위주가 아니다.
현재 기준으로는 `배포 체크리스트`, `일반 배포 가이드`, `GCP 배포 가이드`, `Stripe 설정 문서` 모두 실무 문서로 다시 쓸 수 있는 상태다.

다만 이 문서들은 코드와 테스트 상태에 강하게 묶여 있으므로, 앞으로도 아래 두 조건이 바뀌면 같이 갱신해야 한다.

1. 회귀 테스트 수치가 바뀔 때
2. Stripe/Twilio/Review Booster 운영 경계가 바뀔 때
