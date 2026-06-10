# Pilot Operations Metrics

작성일: 2026-05-18  
목표: 5-10개 managed pilot을 운영하며 self-serve로 열 기능과 managed-only 기능을 분리한다.

## 고객별 기록 항목

- customer_id 또는 account_id
- package_id: `maps_starter`, `calls_growth`, `competitive_market`
- market type: low, normal, competitive
- onboarding blocker
- OAuth blocker
- billing blocker
- content approval blocker
- support minutes per week
- manual operator minutes per week
- AI cost per month
- Twilio/SMS cost per month
- gross margin estimate
- repeated issue tags

## 반복 이슈 태그

- `oauth_gbp_redirect`
- `oauth_instagram_permission`
- `audit_no_listing_match`
- `audit_bad_candidate`
- `payment_card_declined`
- `payment_webhook_delay`
- `content_approval_slow`
- `review_policy_question`
- `sms_consent_missing`
- `manual_data_cleanup`

## Self-serve 후보

- 무료 audit 요청
- dashboard 조회
- billing portal 진입
- review response draft 생성
- report 조회
- contact request 제출

## Managed-only 유지 후보

- GBP/Instagram 연결 복구
- 경쟁 시장 전략 판단
- 고위험 자동 게시
- review policy 판단
- citation cleanup 우선순위
- 고객별 campaign setup
- multi-location reporting setup

## 30일 파일럿 리뷰 질문

1. 고객당 support 시간이 월 몇 시간인가?
2. gross margin이 package별로 충분한가?
3. 고객이 가장 자주 막히는 단계는 어디인가?
4. 자동화보다 사람이 개입해야 결과가 좋아지는 단계는 어디인가?
5. self-serve로 열 경우 환불/지원 부담이 커질 기능은 무엇인가?
6. 다음 10명 고객에게도 같은 package/가격으로 팔 수 있는가?
