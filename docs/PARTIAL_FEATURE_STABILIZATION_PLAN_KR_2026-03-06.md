# Partial Feature Stabilization Plan

작성일: 2026-03-06

## 목적
부분 구현 상태인 기능을 과장 없이 운영 가능한 수준으로 올리기 위한 분석/설계/개발 기준 문서다.
현재 공개 전 기준으로 가장 민감한 기능은 다음 4개다.

- Website SEO
- Instagram Publishing Tools
- Advanced Response Automation
- Q&A Response Drafts

## 1. 현재 판단

### 1.1 Website SEO
상태: 부분 구현

현재 있는 것:
- 메타 태그 생성 API
- 로컬 키워드 제안 API
- 서비스 페이지 생성 API
- 블로그 포스트 생성 API
- 기존 페이지 최적화 분석 API
- 게시용 publish endpoint 틀
- 대시보드 화면

현재 부족한 것:
- 대시보드가 API 실패 시 demo fallback을 보여주던 문제
- 실제 외부 CMS publish 검증 부족
- 결과물 품질 보증 기준 부재
- location 데이터 품질이 낮을 때 결과 편차 큼
- 운영자 승인/검수 흐름 부재

판단:
- "Website SEO가 없다"는 것은 아님
- 하지만 "완성형 Website SEO 제품"이라고 팔 단계는 아님
- 지금은 "Website SEO Tools (Beta)"가 정확한 표현

### 1.2 Instagram Publishing Tools
상태: 부분 구현

현재 있는 것:
- 콘텐츠 생성/승인/게시 흐름
- Instagram 업로드 구조와 관련 플랜 문맥
- 이미지 업로드/교체/삭제 흐름

현재 부족한 것:
- 실제 운영 계정 기준 자동 업로드 신뢰도 검증 부족
- 실패 시 재시도/복구 UX 부족
- 게시 성공/실패 감사 로그 부족

판단:
- "Auto-Upload"보다 "Publishing Tools"가 안전함

### 1.3 Advanced Response Automation
상태: 부분 구현

현재 있는 것:
- 리뷰 응답 자동화 축
- Social Proof / Review Booster / Review Responder와 연결되는 응답 자동화 성격 기능
- 일부 social responder 서비스 뼈대

현재 부족한 것:
- 멀티채널 자동응답 제품 수준의 검증 부족
- 채널별 정책/제약 반영 부족
- 게시/응답 성공률 측정 부족

판단:
- "Social Auto-Responder"보다 "Advanced Response Automation"이 맞음

### 1.4 Q&A Response Drafts
상태: 부분 구현

현재 있는 것:
- 응답 초안 생성 구조와 연관 기능

현재 부족한 것:
- 완전 자동 응답보다는 초안/보조 수준
- 실제 GBP Q&A 운영 검증 부족

판단:
- "Q&A Auto-Response"보다 "Q&A Response Drafts"가 맞음

## 2. 이번 턴에서 반영한 안전 조치

- 공개 가격표에서 과장 표현 축소
- Instagram Auto-Upload -> Instagram Publishing Tools
- Social Auto-Responder -> Advanced Response Automation
- Video Generator 제거
- Website SEO 관련 문구를 Beta/Tools/Workflows 수준으로 하향
- Website SEO 대시보드에서 API 실패 시 demo fallback 제거
- 실패 시 beta 상태 메시지와 실제 오류 흐름 표시

## 3. 안정화 목표 정의

### 공통 목표
- API 실패 시 가짜 성공/가짜 결과를 보여주지 않는다
- 승인/검수 없는 자동 게시 문구를 쓰지 않는다
- 운영자가 실패 원인과 재시도 가능 상태를 확인할 수 있어야 한다
- location/account ownership 검증이 모든 경로에서 유지돼야 한다

### Website SEO 목표
- 메타 태그/키워드/블로그 생성은 실제 결과만 노출
- publish는 지원 CMS가 명확할 때만 활성화
- 결과물 품질 기준과 실패 기준 문서화
- location 데이터 부족 시 사전 검증 메시지 제공

### Instagram Publishing Tools 목표
- 게시 요청/성공/실패 이력 저장
- 실패 재시도 버튼과 운영 로그 제공
- 채널 토큰 상태와 오류 메시지 가시화

### Advanced Response Automation 목표
- 자동응답 범위를 리뷰/소셜 보조 응답으로 한정
- 채널별 자동 발송 정책과 차단 사유 명시
- 승인 전송 여부와 게시 결과 추적

## 4. 개발 우선순위

### P0
- Website SEO dashboard의 demo fallback 제거 유지
- Instagram/response 관련 공개 문구 보수화
- Video Generator 완전 제거

### P1
- Website SEO publish 지원 범위 명시
- Instagram 게시 실패/재시도 상태 모델 추가
- Advanced Response Automation 결과 로그 추가

### P2
- Website SEO 결과 검수 승인 흐름 추가
- Instagram 운영 감사 로그 추가
- 채널별 response automation 정책 화면 추가

## 5. 오픈 기준
다음이 충족되기 전에는 부분 기능을 "완전 자동"으로 마케팅하지 않는다.

- 실제 API 실패 시 가짜 결과 없음
- 운영 로그로 성공/실패 추적 가능
- 재시도 또는 수동 복구 경로 존재
- 최소 파일럿 운영 사례 확보
- 문구가 실제 구현 수준과 일치
