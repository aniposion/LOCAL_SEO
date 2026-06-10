# Local SEO Optimizer 코드 개선 체크리스트

작성일: 2026-03-06
기준 문서: `docs/CODEBASE_ANALYSIS_KR_2026-03-06.md`
최종 갱신 기준: 현재 코드베이스 / 회귀 테스트 `79 passed`

## 1. 목적
이 문서는 코드베이스를 다시 분석해 `문제점만` 추려 실행 가능한 체크리스트로 정리한 문서다. 기능 아이디어는 제외하고, 실제 운영/개발 관점에서 수정해야 할 항목만 남긴다.

## 2. 현재 반영 상태 요약
아래 항목들은 이번 정리 기준으로 이미 상당 부분 반영됐다.

- [x] 주요 라우터 ownership 검증 보강
- [x] `locationId=1` 같은 대표적 하드코딩 제거
- [x] ROI를 location/RevenueProfile 기준으로 전환
- [x] Stripe webhook idempotency 테스트 및 정식 endpoint 정리
- [x] review booster retry, manual requeue, 운영자 알림 추가
- [x] calls의 Twilio SMS/voice webhook 기본 흐름 테스트 추가
- [x] async session 기술부채 일부 핵심 job에서 sync session으로 정리
- [x] 최소 회귀 세트 복구 및 확대 (`79 passed`)

아직 남은 핵심 미완료 항목은 아래 4가지다.
- [ ] 외부 연동의 실제 운영 계정 기준 장애 대응 검증
- [ ] 게시/발행 실패 재시도와 운영 로그 구조의 추가 보강
- [ ] 프론트 전반 UX polish와 empty/error state 마감
- [ ] 운영 audit view / runbook / 모니터링 체계 강화

## 3. 최우선 체크리스트

### 3.1 라우팅 정합성
- [x] 주요 Stripe webhook 정식 경로를 `/api/v1/webhooks/stripe`로 통일했다.
- [x] 프론트 API 경로와 백엔드 라우터 경로의 대표적인 불일치를 정리했다.
- [ ] 모든 API prefix를 전수 기준으로 다시 점검한다.
- [ ] `billing`, `webhooks`, `analytics`, `reviews` 엔드포인트의 최종 공개 경로를 문서와 다시 대조한다.

### 3.2 DB 세션 일관성
- [x] `metric_jobs.py`, `token_jobs.py`, `review_booster_jobs.py`의 async session 기술부채를 핵심 범위에서 정리했다.
- [x] 현재 앱의 기본 ORM 접근은 sync `Session` 기준으로 맞췄다.
- [ ] 나머지 서비스/잡/유틸에도 async 가정이 남아 있는지 전수 점검한다.
- [ ] `get_db`와 실제 ORM 패턴이 완전히 일치하는지 마지막 정리를 한다.

### 3.3 권한 검증
- [x] 주요 location 기반 엔드포인트에 ownership 검증을 추가했다.
- [x] locations, posts, review responder, social proof, review booster, calls에 대한 권한 테스트를 추가했다.
- [ ] admin 전용 라우트와 일반 사용자 라우트를 더 명확히 분리할지 검토한다.
- [ ] 운영자용 수동 복구 API는 audit trail과 함께 다시 점검한다.

### 3.4 프론트 실데이터 연결
- [x] ROI 페이지의 대표적 하드코딩을 제거했다.
- [x] review/social/content/new 등 핵심 화면을 실제 API 기준으로 맞췄다.
- [x] review booster retry 상태와 manual retry를 프론트 목록에 노출했다.
- [ ] 대시보드 전반의 mock chart 및 예시 데이터 잔존 여부를 다시 점검한다.
- [ ] 비어 있는 데이터 상태와 에러 상태 UI를 더 보강한다.

## 4. 백엔드 기능 안정화 체크리스트

### 4.1 게시/발행 파이프라인
- [x] 콘텐츠 생성 -> 승인 -> 게시 흐름의 주요 경로를 실제 코드로 연결했다.
- [x] approval notification 실패 시 resend 경로를 추가했다.
- [ ] 발행 실패 시 재시도 정책을 추가한다.
- [ ] 플랫폼별 실패 원인 로그를 구조화한다.
- [ ] OAuth 토큰 만료/갱신 플로우를 운영 기준으로 더 다듬는다.

### 4.2 리뷰 응답 기능
- [x] 리뷰 응답 pending/approve/reject 기본 흐름을 정리했다.
- [x] ownership 검증과 최소 회귀 테스트를 추가했다.
- [ ] 실제 GBP 게시 운영 검증을 더 한다.
- [ ] 실패 시 `PUBLISHED`, `FAILED`, `PENDING` 상태 정합성을 추가 점검한다.

### 4.3 리뷰 요청 기능
- [x] review booster 기본 발송 흐름과 ownership 검증을 정리했다.
- [x] retry, terminal failure notification, manual requeue를 추가했다.
- [ ] 클릭 추적과 실제 리뷰 유입 연결 키를 더 명확히 정의한다.
- [ ] private feedback와 public review 흐름의 데이터 연결을 정리한다.

### 4.4 놓친 전화 문자 기능
- [x] calls dashboard API와 Twilio SMS/voice webhook 최소 흐름 테스트를 추가했다.
- [x] missed call 처리 경로를 text back 서비스와 연결했다.
- [ ] 실제 Twilio 운영 계정 기준 송신/수신 장애 복구를 점검한다.
- [ ] 자동문자 -> 응답 -> 전환 추적 구조를 더 확장한다.

### 4.5 경쟁사 분석
- [x] UUID/권한 기준 정합성을 맞췄다.
- [ ] Google Places 결과 필드명과 모델 필드를 다시 점검한다.
- [ ] LLM 분석 JSON 파싱 실패 처리를 더 견고하게 만든다.
- [ ] 프론트 소비 경로와 실제 결과 연결 상태를 재확인한다.

### 4.6 소셜 프루프 카드
- [x] placeholder 이미지/문구와 깨진 문자열을 정리했다.
- [x] pending/approve/reject 흐름과 ownership 검증을 정리했다.
- [ ] 카드 승인 후 실제 게시 연동 운영 검증을 더 한다.
- [ ] 외부 이미지 다운로드 timeout/retry 보강 여부를 재검토한다.

## 5. ROI/분석 체크리스트

### 5.1 ROI 계산 로직
- [x] RevenueProfile 모델/API/UI를 연결했다.
- [x] ROI를 시간절감 중심에서 매출형 추정 구조로 확장했다.
- [x] call revenue, review uplift, digital intent를 ROI 화면에 반영했다.
- [ ] 업종별 preset과 실제 업종별 기준값을 더 정교화한다.
- [ ] 실예약/POS 연동 전까지 추정치와 실측치 구분을 더 분명히 한다.

### 5.2 분석 데이터 모델
- [x] metrics/dashboard/weekly report 기본 정합성을 맞췄다.
- [ ] `Analytics`, `AnalyticsEvent`, `Metrics` 역할 중복을 장기적으로 정리한다.
- [ ] dashboard용 summary API와 detail API를 더 명확히 분리한다.

### 5.3 프론트 차트/리포트
- [x] weekly report 생성/전송 기본 흐름을 정리했다.
- [ ] 날짜 포맷/타임존 표시를 화면별로 다시 점검한다.
- [ ] 리포트 다운로드/이메일 전송 UX를 더 다듬는다.

## 6. 결제/구독 체크리스트

### 6.1 플랜/가격 정합성
- [x] 주요 플랜 enum/가격 정합성 오류를 수정했다.
- [ ] billing router, billing service, ROI 계산의 단일 가격 소스를 더 명확히 통합한다.
- [ ] add-on 가격과 Stripe price id 매핑을 운영 환경 기준으로 다시 검증한다.

### 6.2 Stripe webhook
- [x] `/webhooks/stripe`를 정식 endpoint 기준으로 정리했다.
- [x] idempotency 테스트를 추가했다.
- [x] `/webhooks/stripe-legacy`를 hidden + `410 Gone`으로 사실상 제거 단계로 돌렸다.
- [ ] 운영 access log 기준으로 legacy hit 0을 확인한 뒤 path 자체 삭제 여부를 결정한다.
- [ ] 실패 이벤트 재처리 runbook을 더 명확히 한다.

### 6.3 사용량 제한과 AI 비용 제한
- [x] 대표적인 enum/usage 정합성 오류를 수정했다.
- [ ] `RateLimiter`, `credits`, `AiCostService` 규칙을 더 일관되게 정리한다.
- [ ] 사용자에게 보여주는 사용량과 실제 차감 로직 일치 여부를 재검증한다.

## 7. 테스트 체크리스트

### 7.1 현재 확보된 최소 회귀 범위
- [x] health
- [x] locations
- [x] posts
- [x] publish success/failure
- [x] approval state transitions
- [x] billing integration
- [x] Stripe webhook idempotency
- [x] metrics/content/social-proof
- [x] review responder
- [x] review booster
- [x] calls / Twilio SMS / Twilio voice
- [x] jobs

### 7.2 꼭 추가해야 할 테스트
- [ ] OAuth 연결 성공/실패 테스트
- [ ] 실제 외부 publish retry 정책 테스트
- [ ] 운영자 복구 API audit trail 테스트
- [ ] uploads와 storage 실패 복구 테스트

## 8. 문서/인코딩 체크리스트
- [x] `docs/README.md`를 문서 허브로 재작성했다.
- [x] README와 배포 문서를 현재 상태 기준으로 정리했다.
- [x] 주요 깨진 한글 문서를 UTF-8 기준으로 다시 작성했다.
- [ ] 오래된 구현 요약 문서에 최신 상태 배너를 추가한다.
- [ ] legacy 설계 문서를 archive 성격으로 더 명확히 분류한다.

## 9. 코드 품질 체크리스트
- [x] 주요 enum 직렬화/상태값 불일치 오류를 많이 정리했다.
- [x] `datetime.utcnow()` 사용을 핵심 경로와 앱 기준으로 정리했다.
- [ ] 서비스 레이어 공통 예외 타입을 더 정리한다.
- [ ] 문자열 상수와 feature flag를 중앙화한다.
- [ ] 구조화 로그 포맷을 강화한다.

## 10. 운영 체크리스트
- [x] review booster terminal failure 운영자 알림을 추가했다.
- [x] 배포 체크리스트와 리스크 문서를 현재 코드 기준으로 맞췄다.
- [ ] 외부 API 장애 시 fallback 정책을 더 문서화한다.
- [ ] scheduler/job 실패 모니터링을 더 추가한다.
- [ ] 운영자가 문제를 바로 찾을 수 있는 audit view를 설계한다.

## 11. 다음 실행 순서
1. 외부 연동 실제 운영 계정 기준 smoke test 강화
2. publish/storage/OAuth 실패 복구 정책 강화
3. 프론트 empty/error state와 운영자 UX 마감
4. audit log, runbook, 모니터링 체계 보강

## 12. 결론
지금 이 코드베이스의 핵심 문제는 더 이상 `기능 부족`이 아니다.
현재 남은 문제는 `운영 검증`, `실연동 안정성`, `복구 절차`, `마감 품질`이다.

따라서 다음 작업도 새 기능 추가보다 아래 순서가 맞다.
1. 운영 로그와 외부 연동 기준 검증
2. 실패 복구와 모니터링 강화
3. 프론트 운영 품질 마감
4. 이후 업종 특화와 자동화 확장

## 부분 구현 기능 안정화 체크
- [ ] Instagram Publishing Tools 게시 성공/실패 이력 저장
- [ ] Instagram Publishing Tools 재시도/복구 UX
- [ ] Advanced Response Automation 지원 범위 정의
- [ ] Advanced Response Automation 결과 로그 추가
- [ ] Website SEO Tools publish 지원 범위 명시
- [ ] Website SEO Tools 검수/승인 흐름 설계
- [ ] Competitor Analysis freshness/품질 검증
- [ ] Q&A Response Drafts 운영 경로 정의
- [ ] 가격표 문구와 실제 구현 수준 동기화 유지

