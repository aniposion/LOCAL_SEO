# Pricing Partial Feature Backlog

작성일: 2026-03-06
기준: 현재 공개 가격표 문구 + 실제 코드/문서 상태

## 1. 부분 구현으로 분류한 항목

아래 항목들은 "기능이 아예 없음"은 아니지만, 지금 당장 공개 오픈에서 완전 자동/완전 상용 수준으로 말하면 과장될 가능성이 높다.

### 1. Instagram Publishing Tools
상태: 부분 구현
현재 표현: 안전

현재 있는 것:
- 콘텐츠 생성/승인/게시 흐름
- Instagram 업로드 관련 구조
- 이미지 업로드/교체/삭제 흐름

현재 부족한 것:
- 실제 운영 계정 기준 게시 성공률 검증
- 게시 실패 이력/재시도/복구 UX
- 토큰 상태와 채널 오류 가시화
- 게시 감사 로그

오픈 문구:
- 가능: Instagram Publishing Tools
- 금지: Instagram Auto-Upload, Fully Automated Instagram Posting

### 2. Q&A Response Drafts
상태: 부분 구현
현재 표현: 안전

현재 있는 것:
- 응답 초안 생성 흐름과 연관 기능
- 자동응답 보조 성격의 기능 토대

현재 부족한 것:
- 실제 GBP Q&A 게시 운영 검증
- 완전 자동 게시 기준 정책
- 성공/실패 감사 로그

오픈 문구:
- 가능: Q&A Response Drafts
- 금지: Q&A Auto-Response

### 3. Competitor Analysis
상태: 부분 구현
현재 표현: 보수적 검토 필요

현재 있는 것:
- 경쟁사 모델/스키마/API/UI 흐름
- 분석 기본 구조

현재 부족한 것:
- 실제 운영 데이터 품질 검증
- 분석 freshness와 신뢰도 기준
- 결과 설명/추천의 운영 적합성 검증

오픈 문구:
- 가능: Competitor Insights, Competitor Analysis
- 주의: 실시간/완전 자동 경쟁사 인텔리전스처럼 과장 금지

### 4. Website SEO Tools
상태: 부분 구현
현재 표현: 안전

현재 있는 것:
- meta tags 생성
- keyword ideas
- service page/blog generation
- optimize API
- dashboard

현재 부족한 것:
- CMS publish 실운영 검증
- 품질 기준과 승인 흐름
- location 데이터 부족 시 결과 안정성

오픈 문구:
- 가능: Website SEO Tools (Beta)
- 금지: Full Website SEO platform

### 5. Website SEO Workflows
상태: 부분 구현
현재 표현: 안전

현재 있는 것:
- Website SEO Tools 전반
- 생성형 SEO 작업 흐름 일부

현재 부족한 것:
- publish 검증
- 검수/승인
- 결과 품질 측정
- 운영 감사 로그

오픈 문구:
- 가능: Website SEO Workflows (Beta)
- 금지: Full Website SEO

### 6. Advanced Response Automation
상태: 부분 구현
현재 표현: 안전

현재 있는 것:
- Review Responder
- Review Booster
- Social responder 성격 서비스 뼈대
- 일부 자동화/승인/재시도 흐름

현재 부족한 것:
- 멀티채널 자동응답 제품 수준 검증
- 채널별 정책/제약 반영
- 실제 자동 게시 성공률 추적
- 운영 범위 정의

오픈 문구:
- 가능: Advanced Response Automation
- 금지: Social Auto-Responder, Fully Automated DM/Comment Replies

## 2. 현재 자신 있게 말할 수 있는 항목

아래는 부분 구현이 아니라 현재 기준으로 비교적 강하게 설명 가능한 축이다.

- Google Maps posts auto-generation
- Review collection + AI responses
- Basic KPI Dashboard
- Weekly Reports
- Content Scheduler
- Missed Call Text Back
- Review Booster (SMS/Email)

## 3. 지금 오픈 시 개발 우선순위

### P0
- Website SEO: beta 상태 유지 + fake fallback 금지
- Instagram Publishing Tools: 게시 실패/재시도 상태 모델 추가
- Advanced Response Automation: 지원 범위 문서화
- Competitor Analysis: 운영 검증 전까지 분석 품질 주석 노출

### P1
- Instagram publish audit log
- Q&A draft -> approve/send 흐름 정의
- Website SEO publish 지원 범위 명시
- Competitor analysis freshness 표시

### P2
- Website SEO 검수 승인 플로우
- Advanced Response Automation 결과 로그/재시도
- Competitor insight 품질 지표 추가

## 4. 바로 개발할 항목

다음 3개를 먼저 개발 대상으로 잡는 것이 맞다.

1. Instagram Publishing Tools 안정화
2. Advanced Response Automation 경계/로그/실패 복구
3. Website SEO Tools publish/검수/운영 검증

Competitor Analysis와 Q&A Response Drafts는 그 다음이다.
