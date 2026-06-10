# Local SEO Optimizer 주차별 스프린트 계획표

작성일: 2026-03-06
최종 갱신 기준: 현재 코드베이스 / 회귀 테스트 `79 passed`
기준 문서:
- `docs/CODEBASE_ANALYSIS_KR_2026-03-06.md`
- `docs/CODE_IMPROVEMENT_CHECKLIST_KR_2026-03-06.md`
- `docs/REVENUE_CENTRIC_ROI_SPEC_KR_2026-03-06.md`

## 1. 목표
이 계획표의 목적은 제품을 `기능 많은 로컬 마케팅 툴`에서 `자영업 매출 운영 AI`로 전환시키는 것이다.

스프린트 우선순위 기준:
1. 매출 영향도
2. 운영 안정성
3. 사용자 신뢰 회복 속도
4. 기존 코드와의 연결 비용

## 2. 현재 진행 상태 요약
초기 6주 계획 중 상당수 기반 공사는 이미 진행됐다.
현재 상태를 다시 정리하면 아래와 같다.

- 완료 또는 대부분 반영됨
  - ROI location 하드코딩 제거
  - RevenueProfile DB/API/UI 연결
  - metrics, weekly report, locations 실데이터화
  - review responder / social proof / competitor UUID 정리와 권한 검증
  - content/new, approval, resend notification, publish 흐름 연결
  - uploads 실제 업로드/삭제/교체 연결
  - Stripe webhook idempotency 보강
  - review booster retry / manual requeue / 운영자 알림 반영
  - calls Twilio SMS/voice webhook 최소 운영 흐름 정리
  - 최소 회귀 세트 `79 passed`

- 아직 남음
  - 실제 외부 운영 계정 기준 smoke test
  - publish/storage/OAuth 실패 복구 정책 고도화
  - 프론트 empty/error state 마감
  - 운영 audit / runbook / monitoring 강화

## 3. 초기 6주 계획 개요

| 주차 | 스프린트명 | 핵심 목표 | 현재 판단 |
|---|---|---|---|
| 1주차 | ROI 기초 정렬 | ROI/metrics 하드코딩 제거, RevenueProfile 도입 시작 | 대부분 완료 |
| 2주차 | 퍼널 데이터 정리 | 전화/리뷰/게시 흐름의 상태값 정렬 | 대부분 완료 |
| 3주차 | 매출 KPI 구축 | 전화 -> 예약 -> 방문 -> 매출 추정 API 추가 | 기본 완료, 정밀화 필요 |
| 4주차 | 운영 안정화 | 발행, webhook, 재시도, 사용량 제한 정리 | 많이 진척, 운영 검증 남음 |
| 5주차 | 사장님 대시보드 | KPI 중심 홈 재편 | 부분 완료 |
| 6주차 | 업종 특화 1차 | 업종별 프리셋과 기본값 | 시작 전 |

## 4. 남은 2주 실행 우선순위
지금 시점에서는 초기 계획을 그대로 반복하는 것보다, 남은 위험을 줄이는 방식으로 재편하는 것이 맞다.

### Week A. 운영 신뢰도 마감
목표:
- 제한적 파일럿에 필요한 운영 안전망을 더 올린다.

작업 항목:
- 외부 연동 실제 운영 계정 기준 smoke test
- publish/storage/OAuth 실패 복구 정책 보강
- job 실패 알림과 운영 runbook 보강
- Stripe/Twilio 운영 access log 기준 검증

완료 기준:
- 장애가 나도 운영자가 원인과 복구 경로를 바로 알 수 있음

### Week B. 사용자 경험 마감
목표:
- 사장님과 운영자가 실제로 쓰기 쉬운 수준으로 화면을 다듬는다.

작업 항목:
- empty/error/loading state 보강
- review booster retry 상태 필터와 운영자 UX 개선
- ROI 입력과 결과 해석 UX 개선
- dashboard 요약 화면 polish

완료 기준:
- 핵심 화면에서 "눌렀는데 왜 안 되는지 모르겠다"는 상태를 줄임

## 5. 영역별 상세 계획

### ROI / Revenue
이미 반영된 것:
- RevenueProfile 모델/API/UI
- call revenue, review uplift, digital intent 기반 ROI

남은 것:
- 업종별 preset
- 실측치/추정치 구분 강화
- POS/예약 시스템 연결 전략 수립

### Content / Approval / Publish
이미 반영된 것:
- content/new 실제 suggestions/generate 흐름
- draft -> approval -> resend -> publish
- uploads 실제 저장/삭제/교체

남은 것:
- publish retry 정책
- 플랫폼별 실패 로그 구조화
- 운영자 중심 retry/audit 화면

### Reviews / Social / Calls
이미 반영된 것:
- review responder ownership + 상태 전이
- review booster retry / requeue / operator alert
- social proof pending/approve/reject
- Twilio SMS/voice webhook 기본 테스트

남은 것:
- 실제 Twilio/GBP 운영 계정 기준 검증
- review/social publish 운영 확인
- calls 전환 추적 심화

### Billing / Webhooks / Jobs
이미 반영된 것:
- Stripe `/webhooks/stripe` 정리
- webhook idempotency 테스트
- legacy stripe route 사실상 제거 단계
- metric/token/review booster jobs 핵심 정리

남은 것:
- 운영 access log 기준 stripe legacy 사용 여부 최종 확인
- job 실패 모니터링 체계 강화
- billing과 usage 정책 장기 정리

## 6. 매주 공통 검증 항목
- 회귀 테스트가 계속 `79 passed` 이상 유지되는지 확인
- location ownership 검증이 새 기능에도 적용되는지 확인
- 프론트 실데이터 연결이 mock으로 되돌아가지 않는지 확인
- 사용자에게 보이는 문자열과 인코딩이 깨지지 않는지 확인
- 운영 로그와 실패 복구 경로가 같이 남는지 확인

## 7. 현재 기준 최우선 작업
1. 실제 운영 계정 기준 외부 연동 smoke test
2. publish/storage/OAuth 실패 복구 정책
3. 운영 audit / runbook / monitoring 보강
4. 프론트 UX 마감
5. 업종별 preset 설계

## 8. 결론
초기 계획의 앞부분은 이미 많이 진행됐다.
지금 중요한 것은 새 기능을 더 늘리는 것이 아니라, `제한적 파일럿에서 안 깨지는 상태`를 만드는 것이다.

따라서 현재 로드맵은 아래 한 줄로 요약된다.
`기능 확장보다 운영 안정화와 사용자 경험 마감이 우선이다.`

## 부분 구현 기능 안정화 우선순위
- Instagram Publishing Tools 안정화
- Advanced Response Automation 범위/로그/복구 강화
- Website SEO Tools/Workflows beta 안정화
- Competitor Analysis 운영 검증 강화
- Q&A Response Drafts 실제 운영 흐름 정의
- 상세 backlog: docs/PRICING_PARTIAL_FEATURE_BACKLOG_KR_2026-03-06.md

