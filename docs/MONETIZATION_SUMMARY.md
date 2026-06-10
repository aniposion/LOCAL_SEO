# Monetization Summary

최종 갱신 기준: 현재 코드베이스 / 회귀 테스트 `79 passed`

## 1. 한 줄 요약
과금 구조는 이미 코드에 들어와 있고 Stripe 핵심 흐름도 정리됐다. 다만 usage/credits/운영 복구까지 완전히 마감된 상태는 아니다.

## 2. 현재 기준 완료된 것
- 플랜 모델과 가격 정리
- billing router 핵심 경로 연결
- Stripe checkout / portal / subscription 조회 흐름
- Stripe webhook idempotency 테스트
- 배포 문서의 Stripe endpoint 정리
- review booster / calls / ROI 같은 유료 가치 기능 연결

## 3. 현재 기준 부분 완료
- usage summary / usage limits UI와 API
- credits 관련 경로
- add-on 운영 UX
- dunning 운영 가시성
- feature gating 전반의 운영자 관찰성

## 4. 과금 관련 현재 판단
- 파일럿 고객 과금: 가능
- 소수 고객 베타 운영: 가능에 가까움
- broad self-serve 공개 과금: 운영 검증 추가 필요

## 5. 핵심 리스크
1. usage/credits가 아직 demo 성격을 일부 포함함
2. add-on attach/detach 운영 UX가 문서만큼 단순하지 않을 수 있음
3. dunning/operator visibility 강화 필요
4. 가격/기능 설득은 ROI 정밀도와 같이 가야 함

## 6. source of truth
- `app/models/subscription.py`
- `app/routers/billing.py`
- [MONETIZATION_BLUEPRINT.md](./MONETIZATION_BLUEPRINT.md)
- [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md)
- [STRIPE_SETUP.md](./STRIPE_SETUP.md)

## 7. 결론
지금 monetization 상태는 "미구현"도 아니고 "완전 운영 완료"도 아니다.
가장 정확한 표현은 `핵심 과금 흐름은 작동하고, 운영 완성도는 계속 올리는 중`이다.
