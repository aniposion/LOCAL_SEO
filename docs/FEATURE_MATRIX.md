# Feature Matrix

최종 갱신 기준: 현재 코드베이스 / 회귀 테스트 `79 passed`
상태 분류:
- `운영 가능`: 제한적 파일럿 기준으로 핵심 흐름이 연결되고 테스트가 있는 상태
- `부분 완료`: 기능은 연결됐지만 운영 검증 또는 UX 마감이 더 필요한 상태
- `참고용`: 코드나 문서가 아직 현재 기준과 어긋날 수 있는 상태

## 1. 핵심 기능 매트릭스

| 영역 | 현재 상태 | 백엔드 | 프론트 | 테스트 | 메모 |
|---|---|---|---|---|---|
| Authentication | 운영 가능 | 완료 | 완료 | 부분 | 기본 인증 흐름 사용 가능 |
| Locations | 운영 가능 | 완료 | 완료 | 완료 | ownership 테스트 포함 |
| Content / Posts | 운영 가능 | 완료 | 완료 | 완료 | draft, approval, resend, publish 연결 |
| Content New / Suggestions | 운영 가능 | 완료 | 완료 | 완료 | suggestions, generate, draft 생성 연결 |
| ROI / RevenueProfile | 운영 가능 | 완료 | 완료 | 완료 | 매출형 ROI 반영 |
| Metrics / Weekly Reports | 부분 완료 | 완료 | 완료 | 완료 | 운영 계정 기준 검증 추가 필요 |
| Review Responder | 운영 가능 | 완료 | 완료 | 완료 | pending/approve/reject 흐름 포함 |
| Review Booster | 운영 가능 | 완료 | 완료 | 완료 | retry, manual requeue, operator alert 반영 |
| Social Proof | 부분 완료 | 완료 | 완료 | 완료 | 실제 게시 운영 검증 추가 필요 |
| Calls / SMS | 운영 가능 | 완료 | 완료 | 완료 | Twilio SMS/voice webhook 테스트 포함 |
| Competitor Analysis | 부분 완료 | 완료 | 완료 | 부분 | 운영 데이터 품질 검증 추가 필요 |
| Billing / Subscription | 운영 가능 | 완료 | 완료 | 완료 | billing integration + webhook 가드 포함 |
| Stripe Webhooks | 운영 가능 | 완료 | 해당 없음 | 완료 | `/api/v1/webhooks/stripe` 기준 |
| Uploads / Storage | 부분 완료 | 완료 | 완료 | 부분 | 실패 복구와 운영 계정 검증 추가 필요 |
| OAuth / Integrations | 부분 완료 | 완료 | 완료 | 부분 | 실제 운영 계정 smoke test 필요 |
| Admin / Ops | 참고용 | 부분 | 부분 | 없음 | 운영자 audit view 강화 필요 |

## 2. 현재 운영 가능 범위

### 운영 가능
- Locations
- Content / Posts
- ROI / RevenueProfile
- Review Responder
- Review Booster
- Calls / SMS
- Billing / Stripe webhook

### 부분 완료
- Metrics / Weekly Reports
- Social Proof
- Competitor Analysis
- Uploads / Storage
- OAuth / Integrations

### 참고용 또는 차후 고도화
- Admin / Ops audit view
- 업종별 preset
- 실측 POS/예약 연동

## 3. 테스트 커버 기준
현재 핵심 회귀 세트는 아래 영역을 포함한다.

- health
- locations
- posts
- publish success/failure
- approval state transitions
- billing integration
- Stripe webhook idempotency
- metrics
- content
- social-proof
- review-responder
- review-booster
- calls / Twilio SMS / voice
- jobs

기준 수치:
- `79 passed`
- 경고 `0`

## 4. 현재 리스크가 큰 영역
1. 실제 외부 운영 계정 smoke test가 아직 부족한 영역
- OAuth
- Publisher
- Storage
- GBP/Twilio 실운영

2. 운영자 관찰성이 더 필요한 영역
- job 실패 모니터링
- audit trail
- 운영 runbook

3. UX 마감이 필요한 영역
- empty state
- error state
- 운영자 복구 UX

## 5. 읽는 방법
이 문서는 상세 설계 문서가 아니라 `현재 구현 수준을 한 장에서 빠르게 보는 표`다.
상세 판단은 아래 문서를 같이 보는 것이 맞다.

- [CODEBASE_ANALYSIS_KR_2026-03-06.md](./CODEBASE_ANALYSIS_KR_2026-03-06.md)
- [CODE_IMPROVEMENT_CHECKLIST_KR_2026-03-06.md](./CODE_IMPROVEMENT_CHECKLIST_KR_2026-03-06.md)
- [EXECUTION_PRIORITY_ROADMAP_KR_2026-03-06.md](./EXECUTION_PRIORITY_ROADMAP_KR_2026-03-06.md)
- [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md)

## 6. 결론
예전 문서처럼 `전부 완료`로 보는 것은 현재 코드 현실과 맞지 않는다.
지금 기준으로는 `핵심 운영 흐름은 많이 연결됐고`, `실운영 검증과 마감 품질`이 남아 있다고 보는 것이 가장 정확하다.
