# Monetization Readiness Audit

작성일: `2026-03-06`  
최신 반영 기준: `2026-04-01`

## 1. 목적

이 문서는 현재 monetization 구조가 실제로 어디까지 운영 가능한지 냉정하게 판단하기 위한 문서입니다.
핵심 질문은 "과금 기능이 있는가"가 아니라 "과금 후 운영과 복구를 설명할 수 있는가"입니다.

## 2. 현재 verdict

현재 판단은 아래가 가장 정확합니다.

- 내부 데모: 가능
- 제한적 파일럿 과금: 가능
- 소수 고객 베타 과금: 가능에 가까움
- broad public self-serve 과금: 아직 보수적 접근 필요

현재 검증 기준:

- 전체 테스트: `286 passed, 2 warnings`
- 운영 배포 회귀 세트: `120 passed`
- backend import check 통과
- frontend `npm run build`: 통과
- frontend `npm run lint`: 실패, 현재 `161 errors`, `194 warnings`

## 3. 왜 이전보다 좋아졌는가

- Stripe webhook idempotency가 구현돼 있다
- billing integration 테스트가 존재한다
- deployment / Stripe / production 문서가 `2026-04-01` 기준으로 갱신됐다
- smoke test script가 현재 route 기준으로 정리됐다
- review booster retry / requeue / operator alert 같은 운영 가치 기능이 강화됐다

주의:

- canonical backend app route는 `/webhooks/stripe`다
- `/api/v1/...`는 앱 내부 기본 prefix가 아니라 proxy rewrite가 있을 때만 public path로 사용한다

## 4. 아직 막는 요소

1. usage / credits 운영 정책이 broad public 기준으로 완전히 고정되지 않았다
2. dunning / failed payment operator visibility가 더 필요하다
3. 실운영 계정 기준 smoke test와 billing support runbook이 더 필요하다
4. frontend lint debt가 아직 broad public 기준으로 크다

## 5. monetization readiness 분해

| 항목 | 현재 상태 | 판단 |
|---|---|---|
| Plan pricing | 정리됨 | 양호 |
| Stripe checkout | 구현됨 | 양호 |
| Stripe portal | 구현됨 | 양호 |
| Webhook signature / idempotency | 구현 + 테스트 | 양호 |
| Billing integration | 테스트 포함 | 양호 |
| Usage summary | 구현됨 | 부분 완료 |
| Credits purchase / history | 운영 정책 문서화 추가 필요 | 부분 완료 |
| Dunning visibility | 일부 반영 | 부분 완료 |
| Add-on operational UX | 존재하나 운영 검증 더 필요 | 부분 완료 |

## 6. broad public charging 전 non-negotiables

1. usage / credits 정책 고정
2. dunning / operator monitoring 강화
3. subscription 상태 전이와 feature gating 운영 검증
4. billing support / refund / cancellation runbook 정리
5. frontend quality gate 안정화

## 7. 바로 진행할 개선 우선순위

1. frontend lint debt 축소와 release quality gate 정리
2. public API path normalization과 webhook callback 검증
3. billing operator visibility 강화
4. staging 또는 target env에서 실제 token 기반 smoke test 실행
5. 파일럿 로그 기준으로 churn / refund / support load 재평가

## 8. 같이 봐야 하는 문서

- [MONETIZATION_BLUEPRINT.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/MONETIZATION_BLUEPRINT.md)
- [DEPLOYMENT_CHECKLIST.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/DEPLOYMENT_CHECKLIST.md)
- [STRIPE_SETUP.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/STRIPE_SETUP.md)
- [DEPLOYMENT_RISK_ASSESSMENT_KR_2026-03-06.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/DEPLOYMENT_RISK_ASSESSMENT_KR_2026-03-06.md)
- [PRODUCT_COMMERCIALIZATION_CHECKLIST_KR_2026-03-27.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/PRODUCT_COMMERCIALIZATION_CHECKLIST_KR_2026-03-27.md)

## 9. 결론

현재 monetization은 더 이상 "과금 불가" 단계는 아닙니다.
하지만 운영 복구, usage / credits 정합성, self-serve 지원 체계까지 감안하면 `파일럿 / 베타 과금 가능, broad public charging은 추가 운영 검증 후`가 맞습니다.
