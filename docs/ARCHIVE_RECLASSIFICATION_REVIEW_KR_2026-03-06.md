# Archive Reclassification Review

작성일: 2026-03-06
최종 갱신 기준: 현재 코드베이스 / 회귀 테스트 `79 passed`

## 1. 목적
이 문서는 `legacy/참고용` 문서를 실제로 `docs/archive` 아래로 이동할지 검토한 결과와 현재 적용 상태를 정리한다.

## 2. 현재 상태
이번 정리 기준으로 아래 1차, 2차 이동이 실제 반영됐다.

### 1차 이동
- `docs/archive/FRONTEND_IMPLEMENTATION_COMPLETE.md`
- `docs/archive/p0/P0_IMPLEMENTATION_GUIDE.md`
- `docs/archive/p0/P0_RUNBOOK.md`
- `docs/archive/p0/P0_SUMMARY.md`
- `docs/archive/quick-start/QUICK_START_AI_FEATURES.md`
- `docs/archive/quick-start/QUICK_START_KR.md`

### 추가 historical 이동
- `docs/archive/historical/JIRA_TICKETS.md`

즉, 이번 턴 기준으로 `배너 부착 -> 인덱스 분리 -> archive 1차/2차 구조화`까지 진행됐다.

## 3. 왜 전량 이동하지 않았는가

### 3.1 링크 깨짐 리스크
아래 계열은 아직 root `docs`에 두는 편이 낫다.
- `MONETIZATION_*`
- `SPEC_*`
- `AI_FEATURES_*`
- `SYSTEM_ANALYSIS.md`
- `AARRR_*`

이유:
- 현재 기준으로 재작성 완료
- 보조 기준 문서로 아직 활용 가치 있음
- archive로 보내면 오히려 탐색성이 떨어질 수 있음

### 3.2 사용자 관성
IDE 탭, 북마크, 내부 링크가 많은 문서는 한 번에 이동시키면 실사용 흐름이 끊긴다.

## 4. 현재 archive로 이동된 문서 성격
이번에 이동된 대상은 아래 공통점을 가진다.

- 현재 source of truth 역할이 거의 없음
- 실행/배포 판단의 정본이 아님
- 대체 문서가 이미 존재함
- 역사적 참고 가치는 있지만 루트 `docs`에 둘 이유는 약함

## 5. 현재 root docs에 남겨둔 이유가 있는 문서
- `MONETIZATION_*`: 현재 billing/usage 기준으로 재작성됨
- `SPEC_*`: 현재 API 경계 설명 문서로 재정리됨
- `AI_FEATURES_*`: 현재 기능 상태 문서로 재정리됨
- `SYSTEM_ANALYSIS.md`, `AARRR_*`: 현재 상태 평가 문서로 재작성됨

## 6. 다음 후보
추후 추가로 archive 이동을 검토할 수 있는 문서:
- historical audit 계열 중 재작성되지 않은 문서
- 더 이상 참조되지 않는 과거 planning 메모

## 7. 다음 액션
1. archive 이동된 문서 링크/상대경로 안정성 재점검
2. 필요하면 `archive/historical/`를 더 세분화
3. root `docs`에 남은 보조 문서들의 참조 빈도 재확인

## 8. 결론
`docs/archive` 도입과 2차 구조화는 완료됐다.
지금은 추가 대량 이동보다, root `docs`에 남겨 둔 문서들이 `현재 기준 문서`와 `보조 문서` 역할을 제대로 유지하도록 관리하는 것이 더 중요하다.
