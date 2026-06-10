# Spec: Reports / Proof Reporting Boundary

최종 갱신 기준: 현재 코드베이스 / 회귀 테스트 `79 passed`

## 1. 목적
이 문서는 예전의 완성형 before/after PDF UX 목업을 대체한다.
현재는 실제 reports 경계와 weekly report 흐름을 기준으로 읽는 것이 맞다.

## 2. 현재 기준 라우터 경계
현재 사용자-facing reports 경로는 아래다.
- `GET /reports?location_id=...`
- `GET /reports/{report_id}`
- `POST /reports/weekly`

기준 파일:
- `app/routers/reports.py`

## 3. 현재 보고서 구조
현재 보고서 계층은 크게 두 갈래다.

### A. `Report` 기반 보고서
- `/reports` 라우터에서 다루는 목록/상세/주간 생성 경로
- `ReportingService` 기반

### B. `WeeklyReport` 기반 metrics 보고서
- `MetricSnapshot`, `WeeklyReport` 모델 기반
- metrics/dashboard/weekly report 흐름과 연결
- metrics/job 계층과 연결

즉, 예전 문서처럼 `proof reports`만 독립된 하나의 완결 제품으로 보기보다,
현재는 `reports + metrics weekly reporting`이 같이 있는 상태로 보는 것이 맞다.

## 4. 현재 상태 해석
- 목록/상세/생성 기본 경로 존재
- weekly report 생성/전송 흐름 정리됨
- metrics/job과 연동됨
- 다만 과거 문서의 상세 PDF/공유/화이트라벨 UX 전체가 현재 정본으로 확정된 것은 아님

## 5. 권장 읽기 방식
이 문서는 현재부터는 "완성 UX 스펙"이 아니라 `보고서 도메인의 현재 API 경계 설명서`로 본다.
배포 판단은 아래 문서를 같이 본다.
- [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md)
- [FEATURE_MATRIX.md](./FEATURE_MATRIX.md)
- [CODEBASE_ANALYSIS_KR_2026-03-06.md](./CODEBASE_ANALYSIS_KR_2026-03-06.md)
