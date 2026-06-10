# Production Launch Checklist

작성일: `2026-03-28`  
최신 반영 기준: `2026-04-01`

이 문서는 실제 운영 트래픽 직전 마지막으로 확인해야 할 항목만 모은 launch 체크리스트입니다.
현재 기준으로는 `controlled rollout` 문서이며, broad public self-serve launch 완료 선언 문서는 아닙니다.

## 1. 현재 verified baseline

- 전체 테스트: `286 passed, 2 warnings`
- 운영 배포 회귀 세트: `120 passed`
- backend import check: 통과
- frontend `npm run build`: 통과
- frontend `npm run lint`: 실패, 현재 `161 errors`, `194 warnings`
- 현재 rollout 허용 범위: `staging`, `internal demo`, `limited pilot`

## 2. launch stop conditions

아래 중 하나라도 해당되면 launch를 중단합니다.

- [ ] frontend `npm run build` 실패
- [ ] 운영 배포 회귀 세트 미통과
- [ ] `/readyz`가 `503`
- [ ] production에서 SQLite 사용
- [ ] `JWT_SECRET`가 placeholder
- [ ] Stripe / Twilio / OAuth callback 경로가 실제 public URL과 맞지 않음
- [ ] request ID 없이 500이 발생함

## 3. public API path 확인

현재 앱 기준 route:

- `/auth/login`
- `/locations`
- `/metrics/dashboard`
- `/webhooks/stripe`

launch 전 확인:

- [ ] public API가 루트 경로 기준인지 결정했다
- [ ] `/api/v1/...`를 쓴다면 rewrite 규칙이 명시돼 있다
- [ ] Stripe webhook URL이 그 기준과 맞다
- [ ] Twilio callback URL이 그 기준과 맞다
- [ ] `NEXT_PUBLIC_API_URL`이 그 기준과 맞다

## 4. frontend launch gate

```powershell
cd frontend
npm run lint
npm run build
```

현재 상태:

- `npm run build` 통과
- `npm run lint` 실패

launch 전 필요 조건:

- [ ] `npm run build`가 release 과정에서도 안정적으로 유지된다
- [ ] auth / callback / dashboard 경로가 production-safe하다
- [ ] broad public launch 전에 lint debt가 더 줄어든다

## 5. smoke test

`scripts/smoke_test_prod.ps1`는 현재 route 기준으로 갱신됐습니다.

- [ ] 스크립트를 target env에서 실행했다
- [ ] `/healthz`, `/readyz`, `/locations` 확인
- [ ] `billing subscription / usage` 확인
- [ ] location이 있으면 metrics / channels / qa 확인
- [ ] 수동 smoke로 content / approval / review / calls / uploads 흐름 확인

## 6. current verdict

`2026-04-01` 현재 기준:

- `staging`: 가능
- `internal demo`: 가능
- `limited pilot`: 가능
- `broad public rollout`: 보류

보류 이유:

- frontend lint debt
- API path normalization 미정리
- billing / operator support readiness 추가 필요
