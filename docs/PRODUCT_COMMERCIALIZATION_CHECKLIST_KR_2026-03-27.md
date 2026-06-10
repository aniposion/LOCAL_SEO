# Product 상용화 기준 체크리스트

작성일: `2026-03-27`  
최신 반영 기준: `2026-04-01`

## 1. 이 문서의 목적

이 문서는 "기능이 많다"는 이유만으로 상용화하지 않기 위한 `go / no-go 기준`입니다.
상용화는 구현 완료가 아니라, 돈을 받고도 운영과 복구가 가능한 상태인지 판단하는 작업입니다.

핵심 질문은 아래 세 가지입니다.

1. 보안과 권한 경계가 유지되는가
2. 장애가 나도 운영자가 원인 파악과 복구를 할 수 있는가
3. 고객이 첫 가치에 빠르게 도달하고, 실패했을 때 다음 행동을 이해할 수 있는가

## 2. 현재 상용화 판정

`2026-04-01` 기준 현재 판정:

- `staging`: 가능
- `internal demo`: 가능
- `limited pilot`: 가능
- `broad public self-serve rollout`: 보류

현재 검증 기준:

- 전체 테스트: `286 passed, 2 warnings`
- 운영 배포 회귀 세트: `120 passed`
- backend import check 통과
- frontend `npm run build`: 통과
- frontend `npm run lint`: 실패, 현재 `161 errors`, `194 warnings`

## 3. 상용화 단계 정의

### 단계 A. 제한 파일럿 상용화

- 유료 고객을 받을 수는 있지만 수를 제한한다
- founder 또는 운영자가 직접 모니터링한다
- onboarding, 지원, 복구를 사람이 적극 개입해서 보완한다

### 단계 B. 제한 공개

- self-serve 유입을 일부 허용한다
- 지원 문서, 운영 runbook, billing 대응 문서가 준비돼 있다
- onboarding 실패율과 운영 실패율을 추적한다

### 단계 C. 본격 공개 SaaS

- broad self-serve가 가능하다
- founder 개인 대응에 과도하게 의존하지 않는다
- billing, support, incident 대응이 반복 가능한 시스템으로 운영된다

## 4. 지금 당장 개선해야 할 항목

아래는 broad public rollout 전에 우선순위가 가장 높은 항목입니다.

### P0. frontend quality gate 안정화

이유:

- broad public 상용화 직전 가장 직접적인 프런트 품질 리스크입니다.
- build는 회복됐지만 lint debt가 아직 큽니다.

현재 상태:

- `dashboard`와 `integrations callback`의 `useSearchParams()` Suspense 문제를 정리해 `npm run build`는 통과합니다.
- 하지만 lint는 아직 `161 errors`, `194 warnings`입니다.

남은 기준:

- [ ] `npm run build`를 release 과정에서도 계속 유지
- [ ] auth / onboarding / billing / stores 계열 lint debt 축소

### P0. public API path normalization

이유:

- Stripe webhook, Twilio callback, frontend API base URL이 서로 어긋나면 상용화 순간 장애가 납니다.

현재 기준:

- FastAPI 앱 내부 기본 경로는 루트 path입니다.
- `/api/v1/...`는 앱 기본 prefix가 아니라 proxy rewrite가 있는 경우에만 public path로 사용합니다.

남은 기준:

- [ ] public path 기준을 루트 또는 `/api/v1` 중 하나로 고정
- [ ] Stripe / Twilio / frontend / 문서가 같은 기준 사용
- [ ] staging smoke test에서 실제 public URL 검증

### P1. billing 운영성 강화

이유:

- 과금 기능이 있어도 운영자가 구독 상태, 사용량, 실패 결제를 설명하고 복구할 수 없으면 상용화 리스크가 큽니다.

남은 기준:

- [ ] usage / credits 정책을 상품 정책과 맞춰 문서화
- [ ] dunning / failed payment operator visibility 강화
- [ ] billing support runbook 정리
- [ ] refund / churn / usage spike 대응 기준 정리

### P1. operator recovery와 observability 보강

이유:

- 파일럿 단계에서는 통과해도, 공개 상용화는 복구 속도와 추적 가능성이 훨씬 중요합니다.

남은 기준:

- [ ] last success / last failure / retry 상태를 운영 화면에서 더 쉽게 확인
- [ ] request ID와 에러 로그 기준 추적 정착
- [ ] publish / webhook / uploads / notifications 장애 복구 절차 문서화

### P1. self-serve onboarding 품질 개선

이유:

- 상용화는 기능 수보다 "첫 가치까지 걸리는 시간"이 더 중요합니다.

남은 기준:

- [ ] 첫 location 연결이 1회 시도 안에 가능한지 검증
- [ ] fake/demo 데이터가 실제 데이터처럼 보이지 않도록 정리
- [ ] empty / error / reconnect 상태가 다음 행동을 명확히 안내

## 5. 상용화 공통 체크리스트

### 보안 / 권한

- [ ] location ownership 검증이 주요 플로우 전반에 적용된다
- [ ] posts / QA / review / social / calls / billing에서 계정 간 데이터 노출이 없다
- [ ] OAuth token / webhook secret / API key가 하드코딩되지 않는다
- [ ] Stripe webhook signature 검증과 idempotency가 유지된다

### 운영 / 복구

- [ ] publish / approval / webhook / uploads 장애 시 복구 경로가 있다
- [ ] retry / requeue / manual sync가 필요한 곳에 제공된다
- [ ] 운영자가 last failure와 원인 메시지를 확인할 수 있다
- [ ] rollback / migration 실패 대응 절차가 있다

### 사용 경험

- [ ] 첫 가치 도달 시간이 짧다
- [ ] empty state와 error state가 다음 행동을 안내한다
- [ ] reconnect / refresh / retry가 실제 해결 동선으로 이어진다
- [ ] 자동화와 수동 개입 경계가 사용자에게 명확하다

### 수익성 / 지원

- [ ] 고객당 gross margin을 설명할 수 있다
- [ ] usage-heavy 고객에서 Twilio / AI 비용이 통제 가능하다
- [ ] support load가 founder 1인에게 과도하게 몰리지 않는다
- [ ] refund / cancellation / churn 이유를 수집할 수 있다

## 6. 단계별 go / no-go

### 제한 파일럿 상용화 가능 기준

- [ ] 결제 플로우 동작
- [ ] Stripe webhook 정상 동작
- [ ] OAuth / Twilio / uploads 핵심 경로 동작
- [ ] 운영자가 장애를 직접 복구할 수 있음
- [ ] 고객 5~10곳을 직접 관리 가능

### 제한 공개 가능 기준

- [ ] onboarding 실패 원인 분류 가능
- [ ] support 문서와 UI가 주요 질문을 자체 흡수
- [ ] beta 기능이 화면과 문서에서 명확히 구분됨
- [ ] churn / refund / usage spike 대응 기준 존재

### broad public SaaS 가능 기준

- [ ] security review 완료
- [ ] build / deploy / rollback / backup / restore 체계 정비
- [ ] 고객 50+에서도 support load 감당 가능
- [ ] payback / retention / margin 확인
- [ ] founder 직접 대응이 줄어도 운영 가능

## 7. 현재 진행 우선순위

1. frontend lint debt 축소와 quality gate 안정화
2. public API path normalization 완료
3. billing operator visibility와 support runbook 정리
4. staging 실환경 smoke test 실행
5. limited pilot 로그 기반으로 broad public readiness 재평가

## 8. 결론

현재 제품은 "기능 부족으로 상용화 불가" 단계는 아닙니다.
다만 아직은 `제한 파일럿 상용화 가능, broad public self-serve는 보류`가 가장 정확합니다.

다음 판단 전환점은 분명합니다.

- frontend build gate 해결
- public API path 정리 완료
- billing / support / incident 대응 운영성 확보
