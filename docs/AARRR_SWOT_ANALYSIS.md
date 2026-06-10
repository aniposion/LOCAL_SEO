# AARRR / SWOT 분석

작성일: 2026-03-06
최종 갱신 기준: 현재 코드베이스 / 회귀 테스트 `79 passed`

## 1. 목적
이 문서는 제품을 AARRR와 SWOT 관점에서 다시 평가한 문서다.
과거처럼 기능 존재 여부만 보는 문서가 아니라, 현재 운영 준비도와 제품 확장성을 같이 판단하는 용도로 쓴다.

## 2. AARRR 요약

| 영역 | 현재 판단 | 코멘트 |
|---|---|---|
| Acquisition | B | 제품 설명과 가치 제안은 좋지만 실전 유입 체계는 더 필요 |
| Activation | B+ | 첫 가치 경험으로 이어지는 기능은 강함 |
| Revenue | B | 과금 구조는 있으나 self-serve 운영은 더 검증 필요 |
| Retention | B | 반복 사용 유도 기능이 생겼지만 운영 완성도는 더 필요 |
| Referral | C+ | 공유/증명 구조는 있으나 체계적 referral loop는 약함 |

## 3. Acquisition
강점:
- 경쟁사 분석, 리뷰 자동화, 소셜 프루프, ROI 등 메시지 소재가 좋다
- 자영업자 pain point가 분명하다
- before/after 성격의 가치 설명이 가능하다

약점:
- 실전 유입 채널 전략과 landing 체계가 아직 약하다
- product marketing 자산이 코드 수준만큼 강하지 않다

판단:
- 제품 자체는 팔릴 만한 메시지를 갖고 있다.
- 하지만 유입 엔진은 아직 덜 갖춰졌다.

## 4. Activation
강점:
- content generation
- review responder
- social proof
- competitor analysis
- ROI
이 모두 첫 체험 가치로 연결되기 좋다.

현재 상태:
- 실데이터 흐름이 많이 연결되어 있다.
- 사용자가 첫 번째 의미 있는 결과를 보기까지의 거리는 줄어든 상태다.

약점:
- onboarding KPI와 실제 매출 연결성은 더 강화할 필요가 있다.
- product-led activation 문구와 UX는 더 다듬을 여지가 있다.

## 5. Revenue
강점:
- 플랜, 가격, Stripe billing, webhook idempotency가 존재한다.
- 유료 가치를 설명할 수 있는 기능이 많다.
- ROI가 시간절감형에서 매출형 추정 구조로 진화했다.

약점:
- usage/credits 체계는 일부 demo 성격이 남아 있다.
- broad self-serve charging을 위한 운영 완성도는 더 필요하다.

판단:
- 제한적 파일럿/베타 과금은 가능하다.
- 대규모 일반 공개 과금은 운영 검증을 더 해야 한다.

## 6. Retention
강점:
- review booster retry
- weekly report
- notifications
- content publish 흐름
- review/social/calls 운영 흐름

이 기능들은 반복 사용 이유를 만든다.

약점:
- 운영자 관찰성, runbook, audit trail이 약하다.
- 외부 연동 실패 시 사용자 경험이 더 거칠 수 있다.

판단:
- 반복 사용 루프의 뼈대는 생겼다.
- retention을 강하게 만들려면 운영 신뢰도가 더 올라가야 한다.

## 7. Referral
강점:
- proof/report 성격의 결과물을 만들 수 있다.
- social proof는 간접적으로 브랜드 추천 구조를 만든다.

약점:
- 명시적 referral program은 없다.
- case study / 공유 흐름 / 추천 보상 구조가 약하다.

판단:
- referral은 아직 제품의 강점 영역이 아니다.
- 이후 성장 단계에서 별도 설계가 필요하다.

## 8. SWOT

### Strengths
- 자영업자 pain point에 직접 연결되는 기능 폭
- 콘텐츠, 리뷰, 전화, ROI, billing을 한 제품 안에 묶은 구조
- 테스트 기준 `79 passed`
- review booster retry/requeue/operator alert 등 운영 복구 경로 반영

### Weaknesses
- 실운영 외부 계정 기준 검증 부족
- 운영자용 audit / monitoring 약함
- 일부 UX polish 부족
- ROI는 아직 추정치 비중이 큼

### Opportunities
- 업종별 preset
- POS/예약 연동
- 파일럿 기반 케이스 스터디 축적
- agency / multi-location 확장

### Threats
- 외부 플랫폼 정책 변경
- Stripe/Twilio/GBP 장애나 비용 변화
- 실제 운영에서의 신뢰도 부족 시 churn 증가
- 기능은 많지만 운영 복구가 약하면 제품 신뢰 하락

## 9. 현재 전략적 결론
이 제품은 이미 "뭘 만들지" 단계는 지났다.
지금부터는 아래 순서가 맞다.

1. 실운영 검증
2. 복구 절차와 관찰성 강화
3. UX 마감
4. 이후 성장 기능 확장

## 10. 결론
AARRR 관점에서 보면 이 제품은 activation과 revenue 가능성은 높고, retention도 기반이 생겼다.
하지만 acquisition 엔진과 referral 구조는 아직 더 약하다.
SWOT 관점에서는 기능 폭과 방향성이 강점이고, 운영 검증과 마감 품질이 가장 큰 약점이다.
