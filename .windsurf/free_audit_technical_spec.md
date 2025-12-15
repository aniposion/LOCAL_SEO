# Free Audit Module - Technical Specification

## 🎯 Overview

**목적:** 가게 이름만 입력하면 구글 지도 현황을 분석해서 "매월 $X씩 손해 보고 계십니다"라는 PDF 리포트를 생성하는 무료 진단 도구

**전략:** 공포 마케팅(FOMO)으로 유료 전환 유도

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Landing Page (Frontend)                     │
│  [가게 이름 입력] [도시/주 선택] [무료 진단 받기 버튼]            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Free Audit API                              │
│  POST /api/v1/audit/free                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  Google Places  │ │  GBP Scraper    │ │  Competitor     │
│  API            │ │  (Backup)       │ │  Analysis       │
└─────────────────┘ └─────────────────┘ └─────────────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Audit Score Engine                          │
│  - Review Analysis                                               │
│  - Post Frequency Analysis                                       │
│  - Q&A Response Analysis                                         │
│  - Photo Quality Analysis                                        │
│  - Competitor Comparison                                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Report Generator                            │
│  - PDF Generation (WeasyPrint)                                   │
│  - Email Delivery                                                │
│  - Lead Capture (CRM)                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Data Collection Strategy

### Option 1: Google Places API (권장)

```python
# 장점: 공식 API, 안정적, 합법적
# 단점: 일부 데이터 제한 (Q&A, 포스트 등)

from google.maps import places

async def get_place_details(business_name: str, location: str):
    # 1. Place Search로 Place ID 획득
    search_result = await places.search_text(
        query=f"{business_name} {location}",
        language="en"
    )
    
    # 2. Place Details로 상세 정보 획득
    details = await places.get_details(
        place_id=search_result.place_id,
        fields=[
            "name", "rating", "user_ratings_total",
            "reviews", "photos", "opening_hours",
            "website", "formatted_phone_number"
        ]
    )
    return details
```

**수집 가능 데이터:**
- ✅ 평점 (Rating)
- ✅ 리뷰 수 (Review Count)
- ✅ 최근 리뷰 5개
- ✅ 사진 수
- ✅ 영업시간
- ✅ 웹사이트/전화번호
- ❌ 포스트 (GBP API 필요)
- ❌ Q&A (GBP API 필요)
- ❌ Insights (전화/길찾기 - 소유자만)

### Option 2: SerpAPI (Google Maps Scraping)

```python
# 장점: 포스트, Q&A 등 더 많은 데이터
# 단점: 유료, Rate Limit

import serpapi

async def scrape_gbp_data(business_name: str, location: str):
    params = {
        "engine": "google_maps",
        "q": f"{business_name} {location}",
        "type": "search",
        "api_key": settings.serpapi_key
    }
    
    result = serpapi.search(params)
    
    # Place details 추가 조회
    place_params = {
        "engine": "google_maps",
        "type": "place",
        "place_id": result["place_id"],
        "api_key": settings.serpapi_key
    }
    
    details = serpapi.search(place_params)
    return details
```

**수집 가능 데이터:**
- ✅ 모든 Places API 데이터
- ✅ 최근 포스트
- ✅ Q&A 목록
- ✅ 인기 시간대
- ✅ 경쟁사 정보

### Option 3: Hybrid Approach (권장)

```python
# 기본: Google Places API (무료 티어 활용)
# 보조: SerpAPI (상세 분석 필요시)

async def collect_audit_data(business_name: str, location: str):
    # Step 1: Places API로 기본 정보
    basic_info = await google_places.get_details(business_name, location)
    
    # Step 2: 경쟁사 검색 (같은 카테고리, 같은 지역)
    competitors = await google_places.search_nearby(
        location=basic_info.location,
        type=basic_info.category,
        radius=5000  # 5km
    )
    
    # Step 3: 필요시 SerpAPI로 추가 데이터
    if need_detailed_analysis:
        detailed = await serpapi.get_place_details(basic_info.place_id)
        
    return AuditData(
        business=basic_info,
        competitors=competitors[:5],  # Top 5 경쟁사
        detailed=detailed
    )
```

---

## 🧮 Scoring Algorithm

### Audit Score (0-100)

```python
class AuditScoreEngine:
    """비즈니스 GBP 건강도 점수 계산"""
    
    WEIGHTS = {
        "reviews": 0.30,      # 리뷰 점수 (30%)
        "recency": 0.20,      # 최신성 점수 (20%)
        "completeness": 0.20, # 프로필 완성도 (20%)
        "engagement": 0.15,   # 참여도 (15%)
        "competition": 0.15,  # 경쟁력 (15%)
    }
    
    def calculate_review_score(self, data: AuditData) -> float:
        """리뷰 점수 (수량 + 평점 + 최신성)"""
        review_count = data.review_count
        avg_rating = data.rating
        
        # 리뷰 수 점수 (100개 이상 = 만점)
        count_score = min(review_count / 100, 1.0) * 40
        
        # 평점 점수 (4.5+ = 만점)
        rating_score = (avg_rating / 5.0) * 40
        
        # 최근 30일 리뷰 비율
        recent_reviews = data.reviews_last_30_days
        recency_score = min(recent_reviews / 10, 1.0) * 20
        
        return count_score + rating_score + recency_score
    
    def calculate_recency_score(self, data: AuditData) -> float:
        """최신성 점수 (마지막 포스트/활동)"""
        days_since_post = data.days_since_last_post
        
        if days_since_post <= 7:
            return 100
        elif days_since_post <= 14:
            return 80
        elif days_since_post <= 30:
            return 60
        elif days_since_post <= 60:
            return 40
        elif days_since_post <= 90:
            return 20
        else:
            return 0
    
    def calculate_completeness_score(self, data: AuditData) -> float:
        """프로필 완성도"""
        score = 0
        
        if data.has_phone: score += 15
        if data.has_website: score += 15
        if data.has_hours: score += 15
        if data.has_description: score += 15
        if data.photo_count >= 10: score += 20
        elif data.photo_count >= 5: score += 10
        if data.has_menu or data.has_services: score += 20
        
        return score
    
    def calculate_competition_score(self, data: AuditData) -> float:
        """경쟁력 점수 (경쟁사 대비)"""
        my_reviews = data.review_count
        my_rating = data.rating
        
        avg_competitor_reviews = data.avg_competitor_reviews
        avg_competitor_rating = data.avg_competitor_rating
        
        # 리뷰 수 비교
        if my_reviews >= avg_competitor_reviews:
            review_score = 50
        else:
            review_score = (my_reviews / avg_competitor_reviews) * 50
        
        # 평점 비교
        if my_rating >= avg_competitor_rating:
            rating_score = 50
        else:
            rating_score = (my_rating / avg_competitor_rating) * 50
        
        return review_score + rating_score
    
    def calculate_total_score(self, data: AuditData) -> AuditResult:
        """종합 점수 계산"""
        scores = {
            "reviews": self.calculate_review_score(data),
            "recency": self.calculate_recency_score(data),
            "completeness": self.calculate_completeness_score(data),
            "engagement": self.calculate_engagement_score(data),
            "competition": self.calculate_competition_score(data),
        }
        
        total = sum(
            scores[key] * self.WEIGHTS[key] 
            for key in scores
        )
        
        return AuditResult(
            total_score=total,
            breakdown=scores,
            grade=self._get_grade(total),
            estimated_monthly_loss=self._calculate_loss(data, total)
        )
    
    def _calculate_loss(self, data: AuditData, score: float) -> float:
        """예상 월간 손실 계산 (공포 마케팅용)"""
        # 기본 가정: 완벽한 GBP = 월 $5,000 추가 매출 가능
        max_potential = 5000
        
        # 현재 점수 기반 손실 계산
        loss_ratio = (100 - score) / 100
        
        # 경쟁사 대비 손실 추가
        competitor_gap = data.avg_competitor_reviews - data.review_count
        if competitor_gap > 0:
            loss_ratio += min(competitor_gap / 100, 0.3)
        
        estimated_loss = max_potential * loss_ratio
        
        # 최소 $500, 최대 $5,000
        return max(500, min(estimated_loss, 5000))
```

---

## 📄 Report Generation

### PDF Template Structure

```html
<!-- audit_report_template.html -->
<!DOCTYPE html>
<html>
<head>
    <style>
        .score-circle { /* 큰 점수 원형 */ }
        .danger { color: #e74c3c; }
        .warning { color: #f39c12; }
        .success { color: #27ae60; }
        .loss-amount { font-size: 48px; color: #e74c3c; }
    </style>
</head>
<body>
    <header>
        <h1>Google Maps Health Report</h1>
        <h2>{{ business_name }}</h2>
        <p>Generated: {{ date }}</p>
    </header>
    
    <section class="score-overview">
        <div class="score-circle">
            <span class="score">{{ total_score }}</span>
            <span class="grade">{{ grade }}</span>
        </div>
    </section>
    
    <section class="loss-highlight">
        <h2>Estimated Monthly Loss</h2>
        <p class="loss-amount">${{ estimated_loss }}/month</p>
        <p>Based on missed customer opportunities</p>
    </section>
    
    <section class="breakdown">
        <h2>Score Breakdown</h2>
        
        <div class="metric {{ review_status }}">
            <h3>Reviews</h3>
            <p>{{ review_count }} reviews (avg {{ rating }}⭐)</p>
            <p class="issue">{{ review_issue }}</p>
        </div>
        
        <div class="metric {{ recency_status }}">
            <h3>Last Activity</h3>
            <p>{{ days_since_post }} days ago</p>
            <p class="issue">{{ recency_issue }}</p>
        </div>
        
        <!-- 더 많은 메트릭... -->
    </section>
    
    <section class="competitors">
        <h2>How You Compare</h2>
        <table>
            <tr>
                <th>Business</th>
                <th>Reviews</th>
                <th>Rating</th>
            </tr>
            {% for comp in competitors %}
            <tr>
                <td>{{ comp.name }}</td>
                <td>{{ comp.review_count }}</td>
                <td>{{ comp.rating }}⭐</td>
            </tr>
            {% endfor %}
        </table>
    </section>
    
    <section class="cta">
        <h2>Ready to Fix This?</h2>
        <p>Our AI-powered platform can help you:</p>
        <ul>
            <li>✅ Auto-generate engaging posts</li>
            <li>✅ Respond to reviews in seconds</li>
            <li>✅ Track calls & directions</li>
        </ul>
        <a href="{{ signup_url }}" class="button">
            Start Free Trial →
        </a>
    </section>
</body>
</html>
```

---

## 🔌 API Endpoints

### POST /api/v1/audit/free

```python
# app/routers/audit.py

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/audit", tags=["audit"])

class FreeAuditRequest(BaseModel):
    business_name: str
    city: str
    state: str
    email: EmailStr  # 리드 캡처용

class FreeAuditResponse(BaseModel):
    audit_id: str
    status: str  # "processing" | "completed"
    message: str

@router.post("/free", response_model=FreeAuditResponse)
async def request_free_audit(
    request: FreeAuditRequest,
    background_tasks: BackgroundTasks,
):
    """
    무료 GBP 진단 요청
    - 이메일로 PDF 리포트 발송
    - 리드로 CRM에 저장
    """
    # 1. 리드 저장
    lead = await save_lead(request.email, request.business_name)
    
    # 2. 백그라운드에서 분석 실행
    background_tasks.add_task(
        run_audit_and_send_report,
        lead_id=lead.id,
        business_name=request.business_name,
        location=f"{request.city}, {request.state}",
        email=request.email,
    )
    
    return FreeAuditResponse(
        audit_id=str(lead.id),
        status="processing",
        message="Your report will be sent to your email within 5 minutes!"
    )

@router.get("/free/{audit_id}/status")
async def get_audit_status(audit_id: str):
    """진단 상태 확인"""
    audit = await get_audit(audit_id)
    return {
        "status": audit.status,
        "report_url": audit.report_url if audit.status == "completed" else None
    }
```

---

## 📦 Required Dependencies

```txt
# requirements.txt 추가
google-maps-services==4.10.0  # Google Places API
serpapi==0.1.5                # SerpAPI (optional)
weasyprint==60.2              # PDF generation
jinja2==3.1.2                 # Template rendering
```

---

## 🗓️ Implementation Plan

### Phase 1: MVP (1주)
1. Google Places API 연동
2. 기본 점수 계산 로직
3. 간단한 HTML 리포트 (PDF 없이)
4. 이메일 발송

### Phase 2: Enhancement (1주)
1. 경쟁사 분석 추가
2. PDF 리포트 생성
3. 랜딩 페이지 UI

### Phase 3: Optimization (1주)
1. SerpAPI 연동 (상세 데이터)
2. 리드 스코어링
3. 자동 팔로업 이메일

---

## 💡 Key Insights for FOMO Marketing

### 공포 유발 문구 예시

```
🔴 "경쟁사보다 리뷰가 47개 부족합니다"
🔴 "마지막 포스팅이 45일 전입니다 - 고객들이 폐업했다고 생각할 수 있습니다"
🔴 "답변하지 않은 질문 3개 - 잠재 고객이 떠났습니다"
🔴 "매월 약 127명의 고객을 놓치고 있습니다"
💸 "예상 손실: $2,340/월"
```

### CTA 문구

```
"지금 바로 개선 시작하기 - 첫 달 무료"
"경쟁사를 이기세요 - 7일 무료 체험"
"$2,000 대행사 비용을 $149로 줄이세요"
```
