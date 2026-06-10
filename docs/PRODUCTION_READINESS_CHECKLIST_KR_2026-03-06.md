# Local SEO Optimizer 운영 배포 전 최종 체크리스트

작성일: `2026-03-06`  
최신 반영 기준: `2026-04-01`

## 1. 현재 검증 기준

- 전체 테스트: `pytest -q` -> `286 passed, 2 warnings`
- 운영 배포 회귀 세트: `120 passed`
- backend import check 통과
- `python scripts/check_prod_env.py`: 현재 로컬 dev env 기준 errors 없음
- frontend `npm run build`: 통과
- frontend `npm run lint`: 실패, 현재 `161 errors`, `194 warnings`
- 현재 배포 허용 범위: `staging`, `internal demo`, `limited pilot`

## 2. 현재 production blocker

- 프런트 lint 에러와 경고가 여전히 많음
- public API path 문서가 루트 경로와 `/api/v1/...` 기준으로 혼재
- broad public self-serve 기준 billing / operator runbook이 더 필요함

## 3. 배포 차단 항목

아래 중 하나라도 미완료면 공개 운영 배포를 멈춥니다.

- [ ] 운영 배포 회귀 세트가 `120 passed`로 통과했다
- [ ] 전체 테스트가 `286 passed, 2 warnings` 수준을 유지한다
- [ ] `python -c "import app.main; print('ok')"`가 통과한다
- [ ] `alembic upgrade head`가 성공한다
- [ ] frontend `npm run build`가 통과 상태를 유지한다
- [ ] public API path 기준이 하나로 통일돼 있다
- [ ] Stripe / Twilio / frontend / 문서가 같은 public path 기준을 쓴다
- [ ] approval / publish / webhook / uploads 장애 복구 경로가 정리돼 있다

## 4. API path 기준 확인

현재 FastAPI 앱은 `/auth`, `/locations`, `/metrics/dashboard`, `/webhooks/stripe`처럼 루트 경로를 직접 등록합니다.
즉, `/api/v1/...`는 앱 내부 기본 prefix가 아닙니다.

- [ ] 공개 URL이 루트 경로 기준인지 결정했다
- [ ] 공개 URL이 `/api/v1/...`라면 ingress / proxy rewrite 규칙이 문서화됐다
- [ ] Stripe webhook URL이 그 기준과 일치한다
- [ ] Twilio callback URL이 그 기준과 일치한다
- [ ] `NEXT_PUBLIC_API_URL`이 그 기준과 일치한다

## 5. 프런트 확인

- [ ] `npm run build`가 production 모드에서 계속 통과한다
- [ ] lint 부채가 broad public 기준으로 낮아진다
- [ ] auth / onboarding / callback / dashboard 경로가 production-safe하다
- [ ] 주요 화면에서 mock / hardcoded 데이터가 운영값을 가리지 않는다
- [ ] empty / error / reconnect 상태가 다음 행동을 안내한다

## 6. smoke test 확인

`scripts/smoke_test_prod.ps1`는 현재 라우트 기준으로 갱신됐습니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_test_prod.ps1 `
  -BackendBase https://your-backend-domain.com `
  -AccessToken "<JWT>"
```

proxy prefix 예시:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_test_prod.ps1 `
  -BackendBase https://your-backend-domain.com `
  -ApiBase https://your-domain.com/api/v1 `
  -AccessToken "<JWT>"
```

- [ ] smoke script가 staging 또는 target env에서 실제로 실행됐다
- [ ] 실제 계정으로 수동 smoke 확인도 함께 수행됐다

## 7. 현재 판정

`2026-04-01` 기준:

- `staging`: 가능
- `internal demo`: 가능
- `limited pilot`: 가능
- `broad public rollout`: 보류

보류 이유:

- frontend lint debt가 아직 큼
- public API path 문서 정리가 아직 완전하지 않음
- billing / support / operator 운영성 보강이 더 필요함
