# AI Features Index

최종 갱신 기준: 현재 코드베이스 / 회귀 테스트 `79 passed`

## 1. 이 문서의 역할
이 문서는 `AI_FEATURES_*` 문서 묶음의 인덱스다.
예전처럼 "신규 기능 소개" 문서가 아니라, 현재 코드 기준에서 어떤 AI 기능이 어디까지 연결됐는지 빠르게 찾는 용도로 쓴다.

## 2. 현재 기준 AI 기능 묶음
현재 핵심 AI 운영 기능은 아래 4개로 보는 것이 맞다.

1. Competitor Analysis
2. Review Responder
3. Social Proof
4. Review Booster

보조적으로 아래 기능도 AI 운영 흐름에 들어간다.
- Content generation
- Revenue-oriented ROI insights
- Call text back / automation assistance

## 3. 문서 읽기 순서

### 제품/대표/PM
1. [AI_FEATURES_GUIDE_KR.md](./AI_FEATURES_GUIDE_KR.md)
2. [FEATURE_MATRIX.md](./FEATURE_MATRIX.md)
3. [CODEBASE_ANALYSIS_KR_2026-03-06.md](./CODEBASE_ANALYSIS_KR_2026-03-06.md)

### 개발자
1. [AI_FEATURES_GUIDE.md](./AI_FEATURES_GUIDE.md)
2. [IMPLEMENTATION_SUMMARY_AI_FEATURES.md](./IMPLEMENTATION_SUMMARY_AI_FEATURES.md)
3. [CODE_IMPROVEMENT_CHECKLIST_KR_2026-03-06.md](./CODE_IMPROVEMENT_CHECKLIST_KR_2026-03-06.md)

## 4. 현재 구현 상태 요약

| 기능 | 상태 | 현재 메모 |
|---|---|---|
| Competitor Analysis | 부분 완료 | 기본 백엔드/프론트 연결, 운영 검증 추가 필요 |
| Review Responder | 운영 가능 | ownership, approve/reject, 테스트 반영 |
| Social Proof | 부분 완료 | 승인 흐름과 기본 UI 반영, 실제 게시 운영 검증 필요 |
| Review Booster | 운영 가능 | retry, manual requeue, operator alert 반영 |
| AI Content | 운영 가능 | suggestions, generate, approval, publish 연결 |

## 5. source of truth
AI 기능 관련해서 최종 판단은 아래 문서를 우선 본다.

- [FEATURE_MATRIX.md](./FEATURE_MATRIX.md)
- [CODEBASE_ANALYSIS_KR_2026-03-06.md](./CODEBASE_ANALYSIS_KR_2026-03-06.md)
- [CODE_IMPROVEMENT_CHECKLIST_KR_2026-03-06.md](./CODE_IMPROVEMENT_CHECKLIST_KR_2026-03-06.md)

## 6. 참고
예전 `AI_FEATURES_*` 문서들은 기능 소개 성격이 강했고 일부는 당시 구현 상태에 맞춰 과장되거나 오래된 전제가 섞여 있었다.
지금 이 묶음은 `현재 코드와 테스트 기준으로 다시 읽을 수 있게 정리한 보조 문서`라고 보면 된다.
