# ⭐ Local SEO Optimizer – 전체 사용자 여정 (End-to-End UX)

## 페르소나: 미국에서 K-BBQ 식당을 운영하는 사장님

---

## 🎯 0. 페르소나 정보

| 항목 | 내용 |
|------|------|
| **업종** | Korean BBQ Restaurant |
| **Pain Points** | Google Maps 노출 안됨, 전화 응대 못함, 인스타그램 운영 힘듦, 리뷰 답변 못함, 마케팅 시간 없음 |
| **목표** | 손님 더 많이 오게 하고 싶은데 쉬운 방법을 찾는 중 |

---

## 1️⃣ 랜딩 페이지 → "무료 진단 시작하기"

**경로**: `/` (Landing Page)

사장님은 페이스북 광고 or 지인 소개로 랜딩 페이지 방문.

### 화면 메시지:
```
당신의 식당은 Google Maps에서 얼마나 노출되고 있을까요?
무료로 확인해보세요.

📈 전화 · 길찾기 · 리뷰 · 경쟁사 비교 분석
```

### CTA 버튼:
```
[K-BBQ 식당 무료 진단 시작하기]
```

**구현 상태**: ✅ 완료 (`frontend/src/app/page.tsx`)

---

## 2️⃣ 회원가입 (Sign up)

**경로**: `/signup`

- 이메일/비밀번호 입력
- 또는 "Continue with Google" 클릭
- 회원가입 성공 후 자동으로 온보딩 페이지로 이동

**구현 상태**: ✅ 완료 (`frontend/src/app/signup/page.tsx`)

---

## 3️⃣ 온보딩 Step 1 – 비즈니스 정보 입력

**경로**: `/onboarding` (Step 1)

### 입력창:
- **Business Name**: Kim's K-BBQ
- **Address**: (Google Places 자동완성 사용)
- Phone (optional)
- Website (optional)

### 동작:
사장님이 주소를 입력하면 자동으로 Place 후보가 뜸:
```
Kim's Korean BBQ - 123 Main St, Los Angeles, CA
Kim Brothers BBQ - 456 Oak Ave, Los Angeles, CA
K-BBQ House - 789 Pine St, Los Angeles, CA
```

사장님은 자신의 매장 선택.

**구현 상태**: ✅ 완료 (온보딩 Step 1-2)

---

## 4️⃣ 온보딩 Step 2 – AI 분석 실행

**경로**: `/onboarding` (Step 3)

### 화면:
```
지금 K-BBQ 식당의 온라인 상태를 분석하고 있어요 🔍

✔ Google Maps 데이터 수집 중
✔ 경쟁 Korean BBQ 식당들과 비교 중
✔ 리뷰 · 평점 · 최근 활동성 분석 중
✔ 놓치고 있는 전화/방문 기회 계산 중
```

3–5초 후 결과 페이지 로딩.

**구현 상태**: ✅ 완료 (온보딩 Step 3 - Progress Bar + Checklist)

---

## 5️⃣ 온보딩 Step 3 – 상태 진단 결과

**경로**: `/onboarding` (Step 4)

### 화면:
```
📊 K-BBQ 식당 온라인 상태 진단

⭐ 종합 점수: 62 / 100 (등급: B-)

🔥 중요한 문제점 3가지:
1. 최근 45일 동안 Google Posts 업로드 없음
   → Google Maps 노출이 감소하는 주요 원인
2. 리뷰 120개 / 평균 평점 4.1
   → 경쟁 K-BBQ 평균(4.4)보다 낮음
   → 리뷰 응답률 0% = 신뢰도 낮아짐
3. 전화가 많지만 응대를 못 함 (평균 부재중 15–20통/주)
   → Missed Call = 매출 손실로 이어짐

📞 놓치고 있는 기회:
- 매주 전화 중 30~40%는 회신 없음
- 길찾기 클릭 수가 경쟁사 대비 27% 낮음
- Google Maps 포스트 활동성이 0 → 순위 하락 위험

💸 추정 매출 손실: 약 $1,500 ~ $3,000 / 월
```

**구현 상태**: ✅ 완료 (온보딩 Step 4 - Audit Results)

---

## 6️⃣ 온보딩 Step 4 – 해결책 제안 (Local SEO Optimizer)

**경로**: `/onboarding` (Step 5)

### 화면:
```
🎯 이 문제를 해결하는 가장 쉬운 방법은 "Local SEO Optimizer"입니다.

이 서비스가 당신을 위해 자동으로 하는 일:

✔ 1) Google Maps SEO 자동화
   - K-BBQ 업종에 맞는 포스트 자동 생성
   - 이미지 + 본문 + CTA 자동 작성
   - 승인 후 자동 업로드
   - 리뷰 자동 분석 → AI 답변 추천

✔ 2) Instagram 콘텐츠 자동 생성
   - 한국음식/고기구이 스타일 이미지 자동 생성
   - 해시태그 자동 최적화
   - 스케줄 포스팅

✔ 3) KPI 대시보드 제공
   | 항목 | 현재 | 지난주 대비 |
   |------|------|------------|
   | 전화(Call) | 87 | ▲ 21% |
   | 길찾기(Directions) | 64 | ▲ 14% |
   | 리뷰(Reviews) | +3 | — |
   | 프로필 조회수 | 1,093 | ▲ 18% |

✔ 4) 주간 리포트 자동 발송
   - 가장 성과 좋은 포스트
   - 다음 주 추천 홍보 주제
   - 절약한 마케팅 비용($1,851) 자동 계산

✔ 5) Missed Call Text Back (Add-on)
   부재중 전화 발생 시:
   "Sorry we missed your call! Do you want to make a reservation?"
   → 즉시 문자 발송 → 예약 전환 증가
```

**구현 상태**: ✅ 완료 (온보딩 Step 5 - Solution Presentation)

---

## 7️⃣ 마지막 CTA – 무료 체험 시작

**경로**: `/onboarding` (Step 5 - CTA)

### 화면:
```
📈 Google Maps 노출을 20~40% 증가시켜보세요.

지금 시작하시면:
✔ AI 포스트 자동 생성
✔ 리뷰 AI 자동 응답
✔ 전화/길찾기 증가 추적
✔ 인스타그램 자동 업로드
+ 부재중 문자 자동응답(Add-on)

[7일 무료 체험 시작하기]
```

click → Stripe Checkout → Trial 시작.

**구현 상태**: ✅ 완료 (Stripe 연동)

---

## 8️⃣ 결제 완료 후 → 메인 대시보드

**경로**: `/dashboard`

### 대시보드 홈:
```
📊 이번 주 요약
📞 Calls: 21 (▲ 23%)
🗺️ Directions: 18 (▲ 12%)
⭐ New Reviews: +2
📢 Engagement: ▲ 17%

🔥 빠른 액션
- "이번 주 추천 포스트 생성하기"
- "리뷰 2건 응답하기"
- "인스타그램 콘텐츠 확인하기"
```

**구현 상태**: ✅ 완료 (`frontend/src/app/dashboard/page.tsx`)

---

## 9️⃣ 콘텐츠 생성 플로우

**경로**: `/dashboard/content/new`

### 자동 주제 추천 (K-BBQ 전용):
```
🔥 오늘의 추천 주제:
1) 새로운 점심 BBQ 세트 프로모션
2) 생일파티/단체 예약 안내
3) 한국식 바비큐 '고기 굽는 법' 소개
4) 주말 패밀리 세트 할인
5) 인기 메뉴 'LA 갈비' 소개
```

### 플로우:
1. 사장님 주제 선택
2. AI 자동 생성:
   - 본문
   - 이미지 (prompt → realistic food)
   - 해시태그 #kbbq #koreanbbq #foodie
3. 'Approve' 클릭 → Google & Instagram 자동 업로드

**구현 상태**: ✅ 완료 (`frontend/src/app/dashboard/content/new/page.tsx`)

---

## 🔟 리뷰 응답 플로우

**경로**: `/dashboard/reviews`

### 새 리뷰 예시:
```
"고기는 맛있었는데 조금 기다렸어요."
```

### AI 자동 답변 제안 (3개):
```
1. "죄송합니다! 기다리게 해드려 죄송했어요 🙏 다음 방문 시 더 빠르게 안내해드리겠습니다!"
2. "맛있게 드셨다니 기쁩니다! 대기 시간 개선하겠습니다 🙏"
3. "좋은 리뷰 감사드리며 개선 약속드립니다!"
```

사장님 'Send' 클릭 → 바로 게시.

**구현 상태**: ✅ 완료 (`frontend/src/app/dashboard/reviews/page.tsx`)

---

## 1️⃣1️⃣ Missed Call Text Back 자동 동작

**경로**: `/dashboard/calls`

### 동작:
손님이 전화했는데 못 받음 → 5초 후 문자 전송:
```
Hi! Sorry we missed your call at Kim's K-BBQ!
Want to make a reservation today? 🍖🔥
```

손님이 답장하면 자동 응대 or 사장님에게 push 알림

**구현 상태**: ✅ 완료 (`frontend/src/app/dashboard/calls/page.tsx`, `app/routers/calls.py`)

---

## 1️⃣2️⃣ 주간 리포트 (Email + Dashboard)

**경로**: `/dashboard/reports`

### 예시:
```
📊 Kim's K-BBQ Weekly Report

전화(Call): +21%
길찾기(Directions): +14%
프로필 조회: +18%

이번 주 최고의 포스트:
"Weekend Family BBQ Deal"

다음 주 추천 액션:
✔ LA갈비 하이라이트 포스트 1개
✔ 평일 점심 프로모션 포스트 1개
✔ Instagram 릴스 1개
```

**구현 상태**: ✅ 완료 (`frontend/src/app/dashboard/reports/page.tsx`, `app/services/reporting.py`)

---

## 🎉 끝 — 사장님은 마케팅에 손을 거의 안 댄다

### 매주 자동:
- ✅ 포스트 생성
- ✅ 업로드
- ✅ 리뷰 응답
- ✅ KPI 분석
- ✅ 리포트 발송

### 사장님은 Approve 한 번 누르는 것만 하면 됨.

---

## 📊 구현 현황 요약

| 단계 | 페이지 | 상태 |
|------|--------|------|
| 랜딩 | `/` | ✅ 완료 |
| 회원가입 | `/signup` | ✅ 완료 |
| 로그인 | `/login` | ✅ 완료 |
| 온보딩 Step 1-5 | `/onboarding` | ✅ 완료 |
| 대시보드 홈 | `/dashboard` | ✅ 완료 |
| 콘텐츠 생성 | `/dashboard/content/new` | ✅ 완료 |
| 콘텐츠 목록 | `/dashboard/content` | ✅ 완료 |
| 리뷰 관리 | `/dashboard/reviews` | ✅ 완료 |
| Q&A 관리 | `/dashboard/qa` | ✅ 완료 |
| Social 자동응답 | `/dashboard/social` | ✅ 완료 |
| Missed Call | `/dashboard/calls` | ✅ 완료 |
| 리포트 | `/dashboard/reports` | ✅ 완료 |
| 분석 | `/dashboard/analytics` | ✅ 완료 |
| Website SEO | `/dashboard/seo` | ✅ 완료 |
| 위치 관리 | `/dashboard/locations` | ✅ 완료 |
| Agency | `/dashboard/agency` | ✅ 완료 |
| 결제 | `/dashboard/billing` | ✅ 완료 |
| 설정 | `/dashboard/settings` | ✅ 완료 |
| Magic Link 승인 | `/approve/[token]` | ✅ 완료 |
| 비밀번호 찾기 | `/forgot-password` | ✅ 완료 |
| 비밀번호 재설정 | `/reset-password` | ✅ 완료 |

---

## 🔄 자동화 워크플로우

```
┌─────────────────────────────────────────────────────────────┐
│                    Weekly Automation                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Mon 9AM  ─→  AI generates content suggestions              │
│           ─→  Email notification to owner                   │
│                                                             │
│  Owner    ─→  Reviews suggestions (1-click approve)         │
│           ─→  Magic Link approval (no login needed)         │
│                                                             │
│  System   ─→  Auto-publish to GBP                           │
│           ─→  Auto-publish to Instagram                     │
│                                                             │
│  Daily    ─→  Monitor new reviews                           │
│           ─→  Generate AI response suggestions              │
│           ─→  Track calls/directions/views                  │
│                                                             │
│  Realtime ─→  Missed call → SMS auto-response               │
│           ─→  Instagram DM → AI auto-response               │
│                                                             │
│  Sun 6PM  ─→  Generate weekly report                        │
│           ─→  Email report to owner                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 💰 가치 제안 (Value Proposition)

| Before (수동) | After (Local SEO Optimizer) |
|--------------|----------------------------|
| 주 5시간 마케팅 | 주 10분 (승인만) |
| 포스트 0개/월 | 포스트 8-12개/월 |
| 리뷰 응답률 0% | 리뷰 응답률 95%+ |
| 부재중 전화 손실 | SMS 자동 응답 → 예약 전환 |
| 마케팅 비용 $2,000+/월 | $99/월 (Agency: $299) |
