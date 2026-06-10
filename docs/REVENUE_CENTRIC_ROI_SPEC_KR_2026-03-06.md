# Local SEO Optimizer 매출 중심 ROI 설계서

작성일: 2026-03-06
업데이트: DB 모델/API 명세 구체화 반영
최종 갱신 기준: 현재 코드베이스 / 회귀 테스트 `79 passed`

## 1. 목적
기존 ROI는 `시간 절감 금액` 중심이다. 이 문서는 ROI를 `전화`, `예약`, `방문`, `예상 매출`, `예상 이익` 중심으로 재설계하기 위한 상세 명세서다.

핵심 질문:
1. 이 서비스로 전화가 얼마나 늘었는가
2. 그 전화가 예약과 방문으로 얼마나 이어졌는가
3. 예상 매출과 예상 이익이 얼마나 발생했는가
4. 서비스 비용 대비 순기여가 얼마인가

## 2. 현재 구현 반영 상태
이번 정리 기준으로 이미 코드와 연결된 항목은 아래와 같다.

- [x] `RevenueProfile` 모델/스키마/라우터 추가
- [x] `GET /revenue/{location_id}/profile`
- [x] `PUT /revenue/{location_id}/profile`
- [x] `GET /revenue/{location_id}/projection`
- [x] ROI 화면에서 location 전환 및 RevenueProfile 편집
- [x] call revenue, digital intent, review uplift 반영
- [x] weekly report와 metrics 기반 기본 요약 연결

아직 설계 단계에 더 가까운 항목은 아래다.
- [ ] 업종별 preset 자동 적용
- [ ] POS/예약 시스템 실측 연동
- [ ] 추정치와 실측치 저장 계층 분리
- [ ] 업종별 벤치마크와 추천값 자동화

## 3. ROI 레이어 구조

### Layer A. 효율 ROI
- 자동 응답 시간 절감
- 자동 콘텐츠 제작 시간 절감
- 경쟁사 분석 시간 절감
- 소셜 카드 제작 시간 절감

### Layer B. 운영 ROI
- 놓친 전화 회수율
- 리뷰 응답률/응답속도
- 게시 지속률
- 승인 병목 감소

### Layer C. 매출 ROI
- 전화 기반 예약 추정
- 예약 기반 방문 추정
- 방문 기반 결제 추정
- 리뷰/콘텐츠에 의한 간접 매출 기여 추정

## 4. 핵심 데이터 모델

### 4.1 RevenueProfile
목적:
- location별 업종/전환율/객단가/시급 기준을 저장
- ROI 계산의 기본 입력값 역할

실제 구현 경로:
- 모델: `app/models/revenue.py`
- 라우터: `app/routers/revenue.py`
- 스키마: `app/schemas/revenue.py`

필드 명세:

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | UUID | PK |
| `location_id` | UUID | locations.id FK, unique |
| `business_type` | string nullable | 업종명 |
| `currency` | string | 통화, 기본 `USD` |
| `average_order_value` | numeric(10,2) | 평균 객단가 |
| `gross_margin_percent` | numeric(5,2) | 매출총이익률 |
| `call_to_booking_rate` | numeric(5,2) | 전화 -> 예약 전환율 |
| `booking_to_visit_rate` | numeric(5,2) | 예약 -> 방문 전환율 |
| `visit_to_sale_rate` | numeric(5,2) | 방문 -> 결제 전환율 |
| `missed_call_recovery_rate` | numeric(5,2) | 놓친 전화 회수율 |
| `review_to_conversion_lift_percent` | numeric(5,2) | 리뷰 개선이 전환에 미치는 가중치 |
| `owner_hourly_value` | numeric(10,2) | 시간 절감 환산 시급 |
| `created_at` | datetime | 생성시각 |
| `updated_at` | datetime | 수정시각 |

기본값:
- `average_order_value = 150.00`
- `gross_margin_percent = 30.00`
- `call_to_booking_rate = 35.00`
- `booking_to_visit_rate = 80.00`
- `visit_to_sale_rate = 90.00`
- `missed_call_recovery_rate = 20.00`
- `review_to_conversion_lift_percent = 3.00`
- `owner_hourly_value = 50.00`

### 4.2 RevenueProjectionResponse
목적:
- RevenueProfile과 최근 metric snapshot을 기반으로 기본 매출 추정치를 제공

현재 구현된 핵심 응답 필드:
- `location_id`
- `estimated_bookings_from_calls`
- `estimated_visits_from_calls`
- `estimated_sales_from_calls`
- `estimated_revenue_from_calls`
- `estimated_gross_profit_from_calls`
- `missed_call_recovery_revenue`

현재 ROI 화면에서 추가로 반영하는 개념:
- `digital_intent_revenue`
- `review_uplift_revenue`
- `review_uplift_gross_profit`
- `missed_call_recovery_gross_profit`

### 4.3 추후 확장 모델 제안
#### RevenueEvent
권장 추후 추가 필드:
- `event_type`
- `source_channel`
- `source_ref`
- `occurred_at`
- `measured_value`
- `estimated_value`
- `is_estimated`
- `metadata`

이 모델은 향후 실제 결제/예약 데이터 연결 전의 중간 계층으로 적합하다.

## 5. 현재 API 명세

### 5.1 Revenue Profile 조회
`GET /revenue/{location_id}/profile`

설명:
- 해당 location의 RevenueProfile을 조회
- 없으면 기본값으로 자동 생성

### 5.2 Revenue Profile 생성/수정
`PUT /revenue/{location_id}/profile`

설명:
- location별 ROI 입력값 저장
- create/update 겸용

### 5.3 Revenue Projection 조회
`GET /revenue/{location_id}/projection`

설명:
- 최근 `MetricSnapshot` 합계를 기반으로 전화/방문/매출 추정 제공

## 6. 향후 API 확장 명세

### 6.1 Revenue Summary API
권장 endpoint:
`GET /analytics/revenue-summary?location_id=...&days=30`

권장 응답 필드:
- `calls`
- `bookings_estimated`
- `visits_estimated`
- `sales_estimated`
- `revenue_estimated`
- `gross_profit_estimated`
- `subscription_cost`
- `addon_cost`
- `roi_percent`

### 6.2 Revenue Funnel API
권장 endpoint:
`GET /analytics/revenue-funnel?location_id=...&days=30`

권장 응답 필드:
- `impressions`
- `clicks`
- `calls`
- `bookings_estimated`
- `visits_estimated`
- `sales_estimated`
- `conversion_rates`

## 7. 계산식 명세

### 7.1 전화 기반 매출 추정
- `estimated_bookings = calls x (call_to_booking_rate / 100)`
- `estimated_visits = estimated_bookings x (booking_to_visit_rate / 100)`
- `estimated_sales = estimated_visits x (visit_to_sale_rate / 100)`
- `estimated_revenue_from_calls = estimated_sales x average_order_value`
- `estimated_gross_profit_from_calls = estimated_revenue_from_calls x (gross_margin_percent / 100)`

### 7.2 놓친 전화 회수 매출
- `recoverable_calls = missed_calls x (missed_call_recovery_rate / 100)`
- 이후 동일하게 예약/방문/결제 전환 퍼널 적용

### 7.3 리뷰 uplift 추정
- `review_uplift_revenue = baseline_revenue x (review_to_conversion_lift_percent / 100)`

주의:
- 현재는 실측 연결 전이므로 추정치 성격이 강하다.
- 화면과 리포트에서도 `추정치`라는 표현을 유지하는 것이 맞다.

## 8. 프론트/UI 요구사항
현재 반영된 항목:
- ROI 화면에서 location 선택
- RevenueProfile 편집 카드
- Revenue influenced / Call funnel / Digital intent / Review uplift 카드

추가 권장 항목:
- 업종 preset 버튼
- 추정치 vs 실측치 배지
- 값 편집 전후 ROI 변화 diff 표시
- weekly report에 매출 요약 섹션 강화

## 9. 현재 한계와 다음 단계
현재 한계:
- POS/예약/실결제 연동이 없어서 추정치 비중이 큼
- 업종별 benchmark가 아직 수동 입력에 가까움
- 실제 오프라인 방문/결제 검증 계층이 없음

다음 단계:
1. 업종별 preset 추가
2. 예약/POS/콜트래킹 실측 데이터 연결
3. RevenueEvent 계층 설계
4. 추정치/실측치 구분 저장 및 표시 강화

## 10. 결론
이 ROI 설계는 단순한 시간 절감 계산기에서 벗어나, 자영업자가 `AI가 실제로 매출과 이익에 어떤 영향을 줬는지` 보게 만드는 구조다.
현재는 기본 뼈대와 화면 연결까지는 완료됐고, 다음 단계는 `실측 데이터 연결`과 `업종별 정밀화`다.
