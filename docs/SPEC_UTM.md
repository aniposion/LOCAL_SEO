# Spec: UTM / Attribution Boundary

최종 갱신 기준: 현재 코드베이스 / 회귀 테스트 `79 passed`

## 1. 목적
이 문서는 과거의 완성형 UTM page UX 문서를 대체한다.
현재는 UTM과 attribution이 metrics 도메인 안에서 어떻게 위치하는지 설명하는 것이 더 중요하다.

## 2. 현재 구현 중심
현재 코드 기준 UTM/attribution 핵심은 아래다.
- `UTMLink` 모델
- `MetricSnapshot` / `WeeklyReport` 모델과 같은 attribution 묶음
- `MetricsService.generate_utm_link()`
- `MetricsService.get_utm_stats()`
- metrics 관련 라우트에서 dashboard/snapshots/stats 흐름 제공

기준 파일:
- `app/models/metrics.py`
- `app/services/metrics_service.py`

## 3. 현재 문서상 주의점
예전 문서는 `/utm/links`, 상세 click log, export UX를 중심으로 썼다.
하지만 현재 정본은 `metrics + attribution 계층` 쪽에 더 가깝다.
즉, UTM은 독립 제품보다는 아래 역할로 읽는 것이 맞다.

- GBP/post 성과 추적 보조
- attribution/metrics 입력 데이터
- weekly report 및 ROI 보조 신호

## 4. 현재 상태 해석
- UTM 링크 생성 개념 존재
- stats 집계 개념 존재
- attribution 모델 계층 존재
- 다만 예전 문서의 독립 페이지 UX와 모든 세부 endpoint가 현재 그대로 확정되었다고 보기는 어렵다

## 5. 권장 판단 기준
UTM 도메인을 볼 때는 아래를 같이 보는 것이 맞다.
- [FEATURE_MATRIX.md](./FEATURE_MATRIX.md)
- [REVENUE_CENTRIC_ROI_SPEC_KR_2026-03-06.md](./REVENUE_CENTRIC_ROI_SPEC_KR_2026-03-06.md)
- [CODEBASE_ANALYSIS_KR_2026-03-06.md](./CODEBASE_ANALYSIS_KR_2026-03-06.md)

## 6. 결론
UTM은 현재 코드에서 `독립적인 완성 제품 화면`보다는 `metrics / attribution / ROI를 보조하는 데이터 경계`로 이해하는 것이 정확하다.
