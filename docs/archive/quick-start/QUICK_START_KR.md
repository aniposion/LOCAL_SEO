> [!WARNING]
> 이 문서는 legacy/참고용 문서입니다.
> 현재 구현 상태와 다를 수 있으므로, 사용 전 [docs/README.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/README.md), CODEBASE_ANALYSIS_KR_2026-03-06.md, EXECUTION_PRIORITY_ROADMAP_KR_2026-03-06.md, DEPLOYMENT_CHECKLIST.md를 먼저 확인하세요.
# ??鍮좊Ⅸ ?쒖옉 媛?대뱶

5遺??덉뿉 AI 湲곕뒫 ?ъ슜 ?쒖옉?섍린

---

## ?? ?ㅼ튂 諛??ㅼ젙

### 1截뤴깵 ?섏〈???ㅼ튂
```bash
pip install -r requirements.txt
```

### 2截뤴깵 ?섍꼍 蹂???ㅼ젙
`.env` ?뚯씪??異붽?:
```bash
GBP_API_KEY=your_google_places_api_key
GEMINI_API_KEY=your_gemini_api_key
AWS_REGION=us-east-1
S3_BUCKET=your-bucket-name
```

### 3截뤴깵 ?곗씠?곕쿋?댁뒪 留덉씠洹몃젅?댁뀡
```bash
alembic upgrade head
```

### 4截뤴깵 ?쒕쾭 ?쒖옉
```bash
uvicorn app.main:app --reload
```

### 5截뤴깵 API 臾몄꽌 ?뺤씤
http://localhost:8000/docs

---

## ?뱧 湲곕뒫 1: 寃쎌웳??遺꾩꽍

### 媛꾨떒???덉젣
```python
import httpx

async with httpx.AsyncClient() as client:
    # 寃쎌웳??諛쒓껄
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
    
    # 遺꾩꽍 ?앹꽦
    analysis = await client.post(
        "http://localhost:8000/competitor/analyze",
        json={"location_id": 1},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    report = analysis.json()
    print(f"?꾪삊 ?섏?: {report['threat_level']}")
    print(f"?ㅼ썙?? {report['trending_keywords']}")
```

### 寃곌낵 ?덉떆
```
?꾪삊 ?섏?: 以묎컙
?몃젋???ㅼ썙?? ['鍮좊Ⅸ 諛곕떖', '移쒖젅???쒕퉬??, '?좎꽑???щ즺']
異붿쿇 ?≪뀡:
  1. 諛곕떖 ?띾룄 媛쒖꽑 ?꾨줈紐⑥뀡
  2. 吏곸썝 移쒖젅 援먯쑁 媛뺥솕
  3. ?좎꽑???щ즺 SNS ?띾낫
```

---

## ?뮠 湲곕뒫 2: 由щ럭 ?먮룞 ?묐떟

### 媛꾨떒???덉젣
```python
# 由щ럭 ?묐떟 ?앹꽦
response = await client.post(
    "http://localhost:8000/reviews/create-response",
    json={
        "location_id": 1,
        "review_id": "abc123",
        "review_rating": 5,
        "review_text": "?뺣쭚 留쏆엳?댁슂!",
        "platform": "google"
    },
    headers={"Authorization": f"Bearer {token}"}
)

result = response.json()
print(f"AI ?듬?: {result['ai_draft']}")

# ?뱀씤
await client.post(
    f"http://localhost:8000/reviews/{result['id']}/approve",
    json={"response_id": result['id']},
    headers={"Authorization": f"Bearer {token}"}
)
```

### 寃곌낵 ?덉떆
```
AI ?듬?: "?뚯쨷??由щ럭 媛먯궗?⑸땲?? ?뚯떇??留뚯”?ㅻ윭?곗뀲?ㅻ땲 
?뺣쭚 湲곗겑?덈떎. ?욎쑝濡쒕룄 ???섏? 寃쏀뿕???쒓났?섎룄濡?
理쒖꽑???ㅽ븯寃좎뒿?덈떎. ?ㅼ쓬 諛⑸Ц??湲곕??섍쿋?듬땲?? ?삃"

?? grateful
?곹깭: pending ??approved ??published
```

---

## ?렓 湲곕뒫 3: ?뚯뀥 利앸챸 移대뱶

### 媛꾨떒???덉젣
```python
# ?먮룞 移대뱶 ?앹꽦
cards = await client.post(
    "http://localhost:8000/social-proof/auto-generate",
    json={
        "location_id": 1,
        "max_cards": 3,
        "min_rating": 5,
        "days_back": 7
    },
    headers={"Authorization": f"Bearer {token}"}
)

for card in cards.json():
    print(f"移대뱶 URL: {card['final_card_url']}")

# ?뱀씤 諛?寃뚯떆
await client.post(
    f"http://localhost:8000/social-proof/{card['id']}/approve",
    json={
        "card_id": card['id'],
        "publish_immediately": True,
        "platforms": ["instagram"]
    },
    headers={"Authorization": f"Bearer {token}"}
)
```

### ?먮룞???ㅼ젙
```python
# 留ㅼ＜ ?쇱슂?????6???먮룞 ?앹꽦
schedule = await client.post(
    "http://localhost:8000/social-proof/schedule",
    json={
        "location_id": 1,
        "enabled": True,
        "frequency": "weekly",
        "day_of_week": 0,
        "time_of_day": "18:00",
        "max_cards_per_run": 1
    },
    headers={"Authorization": f"Bearer {token}"}
)
```

---

## ?뱤 ?ъ슜???뺤씤

```python
stats = await client.get(
    "http://localhost:8000/usage/stats",
    headers={"Authorization": f"Bearer {token}"}
)

print(stats.json())
```

### ?붽컙 ?쒕룄

| 湲곕뒫 | Starter | Pro | Premium | Agency |
|------|---------|-----|---------|--------|
| 寃쎌웳??遺꾩꽍 | 4??| 4??| 4??| 臾댁젣??|
| 由щ럭 ?묐떟 | 50媛?| 150媛?| 500媛?| 臾댁젣??|
| ?뚯뀥 移대뱶 | 4媛?| 8媛?| 20媛?| 臾댁젣??|

---

## ?렞 ?ㅼ쟾 ?쒖슜 ?щ?

### ?덉뒪?좊옉 二쇨컙 猷⑦떞
```
?붿슂?? 寃쎌웳??遺꾩꽍 蹂닿퀬???뺤씤
???? ??由щ럭???먮룞 ?묐떟
?쇱슂?? 踰좎뒪??由щ럭濡??몄뒪? 移대뱶 ?앹꽦
```

### 誘몄슜???붽컙 猷⑦떞
```
留ㅼ＜: 寃쎌웳 誘몄슜???몃젋???뚯븙
留ㅼ씪: 怨좉컼 由щ럭 利됱떆 ?묐떟
留ㅼ썡: 蹂??由щ럭瑜??뚯뀥 移대뱶濡??쒖옉
```

---

## ?맀 臾몄젣 ?닿껐

### "Invalid API key"
```bash
# .env ?뚯씪 ?뺤씤
cat .env | grep API_KEY
```

### "Rate limit exceeded"
```python
# ?ъ슜???뺤씤
stats = await client.get("/usage/stats")
```

### "Image generation failed"
```bash
# Gemini API ??諛??좊떦???뺤씤
# S3 踰꾪궥 沅뚰븳 ?뺤씤
```

---

## ?뱴 ???뚯븘蹂닿린

- **?꾨꼍 媛?대뱶**: `AI_湲곕뒫_?꾨꼍媛?대뱶.md`
- **援ы쁽 ?곸꽭**: `援ы쁽_?꾨즺_?붿빟.md`
- **API 臾몄꽌**: http://localhost:8000/docs

---

## ?뮕 Pro Tips

1. **罹먯떆 ?쒖슜**: `force_refresh: false`濡?鍮꾩슜 ?덇컧
2. **諛곗튂 泥섎━**: ?щ윭 由щ럭瑜???踰덉뿉 泥섎━
3. **?쇨컙 ?ㅽ뻾**: 遺꾩꽍/?앹꽦 ?묒뾽? 諛ㅼ뿉 ?ㅼ?以?
4. **?ъ슜??紐⑤땲?곕쭅**: ?뺢린?곸쑝濡??쒕룄 ?뺤씤
5. **?ㅼ젣 ?곗씠??*: ?뚯뒪?몃뒗 ?ㅼ젣 由щ럭濡?

---

**?? 以鍮??꾨즺!**

吏湲?諛붾줈 3媛吏 AI 湲곕뒫???ъ슜?대낫?몄슂.

