# Spec: Notifications Boundary

최종 갱신 기준: 현재 코드베이스 / 회귀 테스트 `79 passed`

## 1. 목적
이 문서는 notifications 기능의 현재 API 경계를 설명한다.
과거의 풀 UX 목업 문서가 아니라, 현재 구현된 경로와 아직 mock/demo 성격이 남은 부분을 구분하는 문서다.

## 2. 현재 기준 경계
현재 `/notifications` 라우터는 주로 push notification과 preference/history 진입점을 제공한다.

핵심 경로:
- `GET /notifications/vapid-key`
- `POST /notifications/subscribe`
- `DELETE /notifications/subscribe`
- `GET /notifications/preferences`
- `PUT /notifications/preferences`
- `GET /notifications/history`
- `POST /notifications/history/{notification_id}/read`
- `POST /notifications/history/read-all`
- `POST /notifications/test`

## 3. 현재 상태 해석
- subscription/push preference 뼈대는 존재한다.
- history/read-all 흐름도 경로는 있다.
- 하지만 일부 응답은 demo data 성격이 남아 있다.
- 반면 approval/review/social/review booster 운영 알림은 별도 `NotificationService` 경로로 실제 업무 흐름에 연결된 부분이 있다.

즉, 현재 notifications 도메인은 두 층으로 봐야 한다.

1. `/notifications` 라우터
- 사용자-facing push/prefs/history
- 일부 mock/demo 데이터 포함

2. 서비스 레벨 운영 알림
- approval notifications
- review booster terminal failure alerts
- social proof/review responder 알림
- 실제 운영 흐름에 더 가깝다

## 4. 현재 문서상 주의점
과거 문서의 모든 notification type과 완성형 UX를 현재 정본으로 보면 안 된다.
현재 정본은 `구현된 라우트 + 연결된 서비스`다.

## 5. 추천 참고 문서
- [CODE_IMPROVEMENT_CHECKLIST_KR_2026-03-06.md](./CODE_IMPROVEMENT_CHECKLIST_KR_2026-03-06.md)
- [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md)
- [FEATURE_MATRIX.md](./FEATURE_MATRIX.md)
