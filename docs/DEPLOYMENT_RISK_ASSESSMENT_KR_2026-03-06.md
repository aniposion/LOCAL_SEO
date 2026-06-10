# Local SEO Optimizer 배포 리스크 평가

작성일: `2026-03-06`  
최신 반영 기준: `2026-04-01`

## 1. 요약

현재 상태는 "백엔드는 제한적 운영이 가능한 수준, 프런트는 broad public 기준 품질 게이트가 아직 남아 있는 상태"에 가깝습니다.

현재 허용 가능한 범위:

- `staging`
- `internal demo`
- `limited pilot`

현재 보류해야 하는 범위:

- `broad public self-serve rollout`

## 2. 핵심 검증 결과

- 전체 테스트: `286 passed, 2 warnings`
- 운영 배포 회귀 세트: `120 passed`
- backend import check 통과
- frontend `npm run build`: 통과
- frontend `npm run lint`: 실패, 현재 `161 errors`, `194 warnings`

## 3. 주요 리스크

### 3.1 frontend lint debt

현재 가장 큰 프런트 품질 리스크입니다.

영향:

- broad public release 직전 안정성 신뢰를 낮춤
- auth / onboarding / billing / stores 계열의 타입 안전성이 부족함

심각도: 높음

### 3.2 API path normalization 불일치

현재 FastAPI 앱은 `/auth`, `/locations`, `/metrics/dashboard`, `/webhooks/stripe`처럼 루트 경로를 직접 등록합니다.
반면 일부 문서와 helper 설명에는 `/api/v1/...` 기준이 남아 있습니다.

영향:

- Stripe webhook / Twilio callback / frontend API base URL 설정이 서로 어긋날 수 있음

심각도: 높음

### 3.3 billing / operator runbook 부족

파일럿 운영은 가능하지만 broad public self-serve를 하려면 dunning, refund, failed payment, support 대응이 더 필요합니다.

심각도: 중간

## 4. 완화 요소

- 백엔드 테스트 회귀는 넓고 안정적이다
- Stripe webhook idempotency가 구현돼 있다
- readiness 체크와 환경 검증 스크립트가 있다
- `scripts/smoke_test_prod.ps1`가 현재 route 기준으로 갱신됐다
- frontend `npm run build`가 현재 통과한다

## 5. 남아 있는 실행 항목

1. `frontend/src/lib/api.ts`와 `stores/*`를 중심으로 lint debt 축소
2. public API path 기준을 루트 또는 `/api/v1` 중 하나로 고정
3. Stripe / Twilio / frontend / 문서가 같은 public path를 쓰는지 재검증
4. staging 또는 target env에서 `scripts/smoke_test_prod.ps1`를 실제 token으로 실행
5. billing / dunning / support runbook 보강

## 6. 현재 판단

### 가능

- `staging`
- `internal demo`
- `limited pilot`

### 보류

- `broad public rollout`

보류 근거:

- frontend lint debt가 아직 큼
- public API path 문서 정리가 완전히 끝나지 않음
- billing / support 운영성 보강이 더 필요함
