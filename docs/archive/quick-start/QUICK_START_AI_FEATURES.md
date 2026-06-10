> [!WARNING]
> 이 문서는 legacy/참고용 문서입니다.
> 현재 구현 상태와 다를 수 있으므로, 사용 전 [docs/README.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/README.md), CODEBASE_ANALYSIS_KR_2026-03-06.md, EXECUTION_PRIORITY_ROADMAP_KR_2026-03-06.md, DEPLOYMENT_CHECKLIST.md를 먼저 확인하세요.
# Quick Start: AI Features

Get started with the three new AI features in 5 minutes.

## ?? Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Add to `.env`:
```bash
GBP_API_KEY=your_google_places_api_key
GEMINI_API_KEY=your_gemini_api_key
AWS_REGION=us-east-1
S3_BUCKET=your-bucket-name
```

### 3. Run Migration
```bash
alembic upgrade head
```

### 4. Start Server
```bash
uvicorn app.main:app --reload
```

Visit: http://localhost:8000/docs

---

## ?뱧 Feature 1: Competitor Stealth Watch

**Purpose:** Monitor competitors and get weekly intelligence reports.

### Quick Example
```python
import httpx

async with httpx.AsyncClient() as client:
    # Step 1: Discover competitors
    response = await client.post(
        "http://localhost:8000/competitor/discover",
        json={
            "location_id": 1,
            "radius_miles": 3.0,
            "business_type": "restaurant",
            "max_results": 3
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    competitors = response.json()
    
    # Step 2: Generate analysis
    analysis = await client.post(
        "http://localhost:8000/competitor/analyze",
        json={
            "location_id": 1,
            "force_refresh": False
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    report = analysis.json()
    
    print(f"Threat Level: {report['threat_level']}")
    print(f"Trending Keywords: {report['trending_keywords']}")
    print(f"Recommendations: {report['recommended_actions']}")
```

### What You Get
- ??Top 3 competitors within 3 miles
- ??Trending keywords from their reviews
- ??Threat level assessment
- ??3 actionable recommendations

---

## ?뮠 Feature 2: AI Smart Review Responder

**Purpose:** Auto-generate professional responses to customer reviews.

### Quick Example
```python
# Step 1: Generate response for a review
response = await client.post(
    "http://localhost:8000/reviews/create-response",
    json={
        "location_id": 1,
        "review_id": "review_abc123",
        "review_author": "John Doe",
        "review_rating": 5,
        "review_text": "Amazing food and excellent service!",
        "platform": "google"
    },
    headers={"Authorization": f"Bearer {token}"}
)
review_response = response.json()

print(f"AI Draft: {review_response['ai_draft']}")
print(f"Tone: {review_response['tone']}")
print(f"Status: {review_response['status']}")

# Step 2: Get pending responses
pending = await client.get(
    "http://localhost:8000/reviews/pending?location_id=1",
    headers={"Authorization": f"Bearer {token}"}
)

# Step 3: Approve and publish
approve = await client.post(
    f"http://localhost:8000/reviews/{review_response['id']}/approve",
    json={"response_id": review_response['id']},
    headers={"Authorization": f"Bearer {token}"}
)
```

### What You Get
- ??Sentiment analysis
- ??Intent detection
- ??Professional, empathetic responses
- ??Approval workflow
- ??Auto-publish to Google Business Profile

---

## ?렓 Feature 3: Neighborhood Social Proof

**Purpose:** Convert 5-star reviews into Instagram-ready cards.

### Quick Example
```python
# Step 1: Auto-generate cards from best reviews
cards = await client.post(
    "http://localhost:8000/social-proof/auto-generate",
    json={
        "location_id": 1,
        "max_cards": 3,
        "min_rating": 5,
        "min_text_length": 50,
        "days_back": 7
    },
    headers={"Authorization": f"Bearer {token}"}
)

for card in cards.json():
    print(f"Card URL: {card['final_card_url']}")
    print(f"Title: {card['card_title']}")

# Step 2: Get pending cards
pending = await client.get(
    "http://localhost:8000/social-proof/pending?location_id=1",
    headers={"Authorization": f"Bearer {token}"}
)

# Step 3: Approve card
approve = await client.post(
    f"http://localhost:8000/social-proof/{card['id']}/approve",
    json={
        "card_id": card['id'],
        "publish_immediately": True,
        "platforms": ["instagram"]
    },
    headers={"Authorization": f"Bearer {token}"}
)

# Step 4: Set up weekly automation
schedule = await client.post(
    "http://localhost:8000/social-proof/schedule",
    json={
        "location_id": 1,
        "enabled": True,
        "frequency": "weekly",
        "day_of_week": 0,  # Sunday
        "time_of_day": "18:00",
        "min_rating": 5,
        "max_cards_per_run": 1,
        "auto_approve": False
    },
    headers={"Authorization": f"Bearer {token}"}
)
```

### What You Get
- ??AI-generated background images (Imagen 3)
- ??1080x1080 Instagram-ready format
- ??Professional text overlay
- ??Weekly automation
- ??S3-hosted images

---

## ?뵏 Rate Limits

Check your usage:
```python
stats = await client.get(
    "http://localhost:8000/usage/stats",
    headers={"Authorization": f"Bearer {token}"}
)
print(stats.json())
```

### Monthly Limits by Plan

| Feature | Starter | Pro | Premium | Agency |
|---------|---------|-----|---------|--------|
| Competitor Analysis | 4 | 4 | 4 | ??|
| Review Responses | 50 | 150 | 500 | ??|
| Social Proof Cards | 4 | 8 | 20 | ??|

---

## ?렞 Common Use Cases

### Use Case 1: Weekly Competitor Check
```python
# Run every Monday
analysis = await client.post("/competitor/analyze", json={
    "location_id": location_id,
    "force_refresh": True
})

# Email report to owner
send_email(owner_email, analysis.json())
```

### Use Case 2: Auto-Respond to Reviews
```python
# Webhook receives new review
@app.post("/reviews/webhook")
async def handle_review(payload: dict):
    # Generate response
    response = await client.post("/reviews/create-response", json=payload)
    
    # Send notification to owner
    send_notification(owner_id, response.json())
```

### Use Case 3: Sunday Social Media Prep
```python
# Run every Sunday at 6pm
cards = await client.post("/social-proof/auto-generate", json={
    "location_id": location_id,
    "max_cards": 1,
    "min_rating": 5,
    "days_back": 7
})

# Notify owner to approve
send_notification(owner_id, cards.json())
```

---

## ?맀 Troubleshooting

### Error: "Invalid API key"
```bash
# Check .env file
cat .env | grep GBP_API_KEY
cat .env | grep GEMINI_API_KEY
```

### Error: "Rate limit exceeded"
```python
# Check usage
stats = await client.get("/usage/stats")
print(stats.json())

# Upgrade plan or wait for monthly reset
```

### Error: "Image generation failed"
```bash
# Check Gemini API quota
# Verify S3 bucket permissions
# Check logs for detailed error
```

---

## ?뱴 Next Steps

1. **Read Full Documentation:** `AI_FEATURES_GUIDE.md`
2. **Review Implementation:** `IMPLEMENTATION_SUMMARY_AI_FEATURES.md`
3. **Test Endpoints:** http://localhost:8000/docs
4. **Set Up Webhooks:** Configure Google Business Profile webhooks
5. **Schedule Jobs:** Add to worker scheduler

---

## ?뮕 Pro Tips

1. **Cache competitor data** - Use 7-day cache to save API costs
2. **Batch process reviews** - Process multiple reviews at once
3. **Schedule during off-hours** - Run analysis/generation at night
4. **Monitor usage** - Check limits regularly
5. **Test with real data** - Use actual reviews for best results

---

## ?넊 Need Help?

- **API Docs:** http://localhost:8000/docs
- **Full Guide:** `AI_FEATURES_GUIDE.md`
- **Issues:** GitHub Issues
- **Email:** support@localseo.app

---

**Ready to go! ??**

Start with one feature, test it thoroughly, then expand to others.

