# AI 기능 가이드

최종 갱신 기준: 현재 코드베이스 / 회귀 테스트 `79 passed`

## 1. 목적
이 문서는 현재 코드 기준에서 AI 기능 묶음이 실제로 어디까지 구현되어 있는지 설명하는 문서다.
예전처럼 기능 소개 위주 문서가 아니라, 현재 구현 상태를 반영하는 안내서로 읽는 것이 맞다.

## 2. 현재 AI 기능 묶음

### 2.1 Competitor Analysis
목적:
- 주변 경쟁사 발견
- 주간 경쟁 인텔리전스 생성
- 키워드, 평점, 위협도 인사이트 제공

현재 상태:
- 백엔드와 프론트 기본 연결 존재
- UUID 및 ownership 정합성 정리
- 다만 Google Places 결과 품질과 운영 검증은 더 필요

### 2.2 Review Responder
목적:
- AI 초안 생성
- 승인 워크플로우
- 승인 후 게시

현재 상태:
- pending / approve / reject 흐름 연결
- ownership 검증 반영
- 회귀 테스트로 핵심 흐름 고정
- 실제 GBP 게시 운영 검증은 더 필요

### 2.3 Social Proof
목적:
- 긍정 리뷰를 카드형 콘텐츠로 변환
- 승인 후 활용

현재 상태:
- 생성, pending, approve/reject 흐름 반영
- placeholder/깨진 문자열 정리
- UUID/권한 정합성 정리
- 다만 실제 게시 운영 검증과 외부 자산 안정성은 추가 필요

### 2.4 Review Booster
목적:
- SMS/이메일 리뷰 요청 발송
- 요청 상태 추적
- 실패 시 복구

현재 상태:
- campaign, request, opt-out, feedback, ownership 흐름 연결
- retry 정책 반영
- manual requeue 반영
- terminal failure 운영자 알림 반영
- 프론트 목록에서 retry 상태와 재큐 버튼 노출

### 2.5 AI Content Support
목적:
- suggestions와 생성 기능으로 초안 만들기
- approval과 publish 흐름으로 연결

현재 상태:
- suggestions / generate / draft 생성 연결
- draft -> approval -> resend notification -> publish 연결
- 업로드 흐름 연결
- publish retry와 채널별 실패 복구는 더 강화 필요

## 3. 현재 구현 상태 표

| 기능 | 상태 | 메모 |
|---|---|---|
| Competitor Analysis | 부분 완료 | 기반은 좋지만 운영 검증 필요 |
| Review Responder | 파일럿 운영 가능 | 핵심 흐름과 테스트 반영 |
| Social Proof | 부분 완료 | 승인 흐름은 됐고 게시 운영 검증 남음 |
| Review Booster | 파일럿 운영 가능 | retry와 운영 복구 경로 포함 |
| AI Content | 파일럿 운영 가능 | 생성/승인/게시 핵심 흐름 연결 |

## 4. 현재 무엇이 검증됐는가
회귀 테스트 기준으로 아래 인접 영역이 이미 포함된다.
- review responder
- social proof
- review booster
- content 생성 진입 흐름
- jobs
- ownership boundary
- Stripe/Twilio 인접 운영 흐름

기준 수치:
- `79 passed`
- 경고 `0`

## 5. 아직 완전히 증명되지 않은 것
- 실제 플랫폼 운영 계정 기준 게시/복구 동작
- 외부 OAuth 복구의 실운영 검증
- POS/실예약 기준 ROI 실측 검증
- 운영자 audit / recovery UX polish

## 6. 같이 읽어야 할 문서
- [AI_FEATURES_INDEX.md](./AI_FEATURES_INDEX.md)
- [FEATURE_MATRIX.md](./FEATURE_MATRIX.md)
- [CODEBASE_ANALYSIS_KR_2026-03-06.md](./CODEBASE_ANALYSIS_KR_2026-03-06.md)
- [CODE_IMPROVEMENT_CHECKLIST_KR_2026-03-06.md](./CODE_IMPROVEMENT_CHECKLIST_KR_2026-03-06.md)

## 7. 결론
현재 AI 기능 묶음은 더 이상 개념이나 데모 수준이 아니다.
핵심 흐름은 코드, UI, 테스트에 같이 반영됐다. 남은 일은 기능 추가보다 `실운영 검증`, `복구 경로`, `마감 품질`을 높이는 것이다.
