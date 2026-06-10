# 시스템 분석 문서

작성일: 2026-03-06
최종 갱신 기준: 현재 코드베이스 / 회귀 테스트 `79 passed`

## 1. 목적
이 문서는 현재 코드베이스의 구조, 연결 상태, 운영 리스크를 빠르게 파악하기 위한 내부 시스템 분석 문서다.
상세 구현 문서가 아니라 `어떤 시스템이 어느 정도까지 연결됐는지` 보는 용도로 쓴다.

## 2. 시스템 한 줄 요약
이 프로젝트는 단순 로컬 SEO 도구가 아니라 `자영업자용 AI 운영 보조 SaaS`다.
핵심 목표는 사장님이 직접 처리하던 반복 운영 업무를 AI와 자동화 흐름으로 줄이고, 최종적으로 매출과 현장 운영에 집중하게 만드는 것이다.

## 3. 시스템 구조

### 3.1 프론트엔드
- `Next.js`
- 대시보드 중심 구조
- API 클라이언트는 `frontend/src/lib/api.ts`, `frontend/src/lib/api/ai-features.ts` 기준

현재 상태:
- 핵심 운영 화면 다수가 실데이터 기준으로 정리됨
- 일부 화면은 UX polish와 empty/error state 보강이 더 필요

### 3.2 백엔드
- `FastAPI`
- `SQLAlchemy`
- `Alembic`
- 도메인별 router/service/model 구조

주요 도메인:
- auth / account / location
- content / posts / approval
- review responder / review booster / social proof
- metrics / reports / ROI / revenue
- billing / webhooks / usage
- calls / uploads / integrations

### 3.3 데이터 계층
- UUID 기반 location/account 구조 정리
- metrics / utm / weekly report 모델 존재
- RevenueProfile 기반 ROI 입력 저장 구조 존재

### 3.4 외부 연동
- Google Business Profile
- Stripe
- Twilio
- OpenAI / Gemini 계열
- Storage

평가:
- 구조는 충분히 넓다.
- 실제 운영 계정 기준 smoke test와 복구 절차는 더 필요하다.

## 4. 핵심 운영 흐름

### 4.1 콘텐츠 흐름
`AI 생성 -> draft -> approval 요청 -> resend notification -> publish`

현재 상태:
- 실제 API와 프론트 흐름 연결
- 업로드 이미지 저장/삭제/교체 포함
- publish success/failure 테스트 존재

### 4.2 리뷰 운영 흐름
- `review responder`: AI 응답 초안 생성, approve, reject
- `review booster`: campaign, request send, opt-out, feedback, retry, manual requeue

현재 상태:
- ownership 검증 정리
- retry와 운영자 알림까지 반영
- 핵심 테스트 확보

### 4.3 소셜 프루프 흐름
- 카드 생성
- pending 목록
- approve / reject

현재 상태:
- UUID 정리 완료
- 기본 승인 흐름과 프론트 연결 완료
- 실제 게시 운영 검증은 추가 필요

### 4.4 전화/문자 흐름
- thread 조회
- 메시지 전송
- Twilio SMS inbound/status webhook
- Twilio voice missed call webhook
- missed call text back 연결

현재 상태:
- calls와 webhook 최소 운영 흐름 테스트 확보
- 실제 Twilio 운영 계정 기준 검증은 더 필요

### 4.5 매출형 ROI 흐름
- RevenueProfile 저장
- call revenue 추정
- digital intent 추정
- review uplift 추정
- gross profit / ROI 계산

현재 상태:
- DB/API/UI 연결 완료
- 실측 POS/예약 연동은 아직 아님

## 5. 현재 강점
- 핵심 플로우가 문서가 아니라 실제 코드와 DB에 연결되어 있다.
- UUID, enum, session, webhook 정합성이 이전보다 많이 개선됐다.
- Stripe webhook idempotency와 Twilio webhook 최소선이 테스트에 포함됐다.
- review booster retry / manual requeue / operator alert까지 반영됐다.
- 회귀 기준이 `79 passed`까지 확대됐다.

## 6. 현재 리스크

### 6.1 실운영 검증 부족
- GBP/Twilio/Storage/OAuth 실운영 계정 smoke test
- publisher 실패 복구
- 운영 access log 기반 검증

### 6.2 운영자 관찰성 부족
- audit view
- runbook
- job 실패 모니터링

### 6.3 UX 마감 부족
- empty/error/loading state
- 운영자 복구 UX
- 일부 대시보드 polish

## 7. 현재 단계 판단
- 프로토타입: 지남
- 실사용 가능한 베타: 가까움
- 제한적 파일럿 운영: 가능
- 일반 공개 운영: 아직 보수적 접근 필요

## 8. 다음 우선순위
1. 외부 연동 실운영 smoke test 강화
2. publish/storage/OAuth 실패 복구 정책 강화
3. audit / runbook / monitoring 보강
4. 프론트 UX 마감
5. 업종별 preset 및 실측 데이터 연동 전략

## 9. 결론
이 시스템은 더 이상 기능만 많은 프로토타입이 아니다.
핵심 운영 플로우는 이미 연결됐고, 테스트 기반 안전망도 상당 부분 생겼다.
이제 중요한 것은 기능 추가보다 `실운영에서 안 깨지는 구조`와 `운영자가 복구할 수 있는 구조`를 만드는 일이다.
