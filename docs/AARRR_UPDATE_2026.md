# AARRR 업데이트 2026

작성일: 2026-03-06
최종 갱신 기준: 현재 코드베이스 / 회귀 테스트 `79 passed`

## 1. 목적
이 문서는 이전 AARRR 분석 이후 무엇이 실제로 바뀌었는지 요약한다.
핵심은 제품의 성장 가능성보다 `현재 구현과 운영 준비도가 얼마나 올라왔는지`를 보는 것이다.

## 2. 이전 대비 큰 변화

### 2.1 Revenue 측면
- Stripe webhook idempotency 보강
- billing integration 테스트 반영
- billing 문서와 Stripe 경계 정리
- monetization 문서 재작성

의미:
- 예전보다 과금 구조를 더 신뢰할 수 있게 됐다.
- 다만 broad self-serve readiness까지 간 것은 아니다.

### 2.2 Activation 측면
- content/new 실동작 흐름 정리
- draft -> approval -> publish 흐름 정리
- ROI와 RevenueProfile UI 연결

의미:
- 사용자가 가입 후 실제 가치를 보는 속도가 더 빨라졌다.

### 2.3 Retention 측면
- review booster retry 정책
- manual requeue
- terminal failure operator alert
- Twilio SMS/voice webhook 흐름 테스트

의미:
- 자동화가 실패했을 때 그대로 멈추는 구조가 줄었다.
- 운영 신뢰도를 올리는 방향의 변화다.

### 2.4 Analytics / Proof 측면
- metrics / weekly report / ROI 화면 정리
- RevenueProfile 기반 매출형 추정 구조 반영

의미:
- 제품 가치 설명이 "AI가 뭔가 해줌" 수준에서 "매출 영향" 쪽으로 옮겨갔다.

## 3. 현재 AARRR 업데이트 요약

| 영역 | 이전 인상 | 현재 인상 |
|---|---|---|
| Acquisition | 메시지는 있으나 구조 약함 | 여전히 약한 편, product marketing 과제 남음 |
| Activation | 기능은 많으나 연결이 거칠었음 | 핵심 흐름 연결이 좋아짐 |
| Revenue | billing 신뢰도 부족 | 파일럿 과금 가능 수준으로 개선 |
| Retention | 기능은 있으나 실패 복구 약함 | retry/requeue/alert로 개선 |
| Referral | 거의 없음 | 여전히 약함 |

## 4. 현재 제품 단계
- 프로토타입: 지남
- 실사용 가능한 베타: 가까움
- 제한적 파일럿: 가능
- 일반 공개 운영: 운영 검증 더 필요

## 5. 다음 AARRR 개선 포인트
1. Acquisition
- landing / case study / proof assets 강화

2. Activation
- onboarding KPI와 실제 매출 연결 강화

3. Revenue
- usage/credits 운영 정책 고정
- self-serve billing 운영 검증 강화

4. Retention
- runbook / audit / monitoring 보강

5. Referral
- 공유 루프와 추천 프로그램 설계

## 6. 결론
이번 업데이트의 핵심은 기능 수 증가가 아니라 `운영 가능한 흐름이 늘었다`는 점이다.
AARRR 중에서 가장 많이 좋아진 영역은 Revenue와 Retention이고, 가장 더 필요한 영역은 Acquisition과 Referral이다.
