> [!WARNING]
> 이 문서는 legacy/참고용 문서입니다.
> 현재 구현 상태와 다를 수 있으므로, 사용 전 [docs/README.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/README.md), CODEBASE_ANALYSIS_KR_2026-03-06.md, EXECUTION_PRIORITY_ROADMAP_KR_2026-03-06.md, DEPLOYMENT_CHECKLIST.md를 먼저 확인하세요.
# P0 Implementation Guide - MVPL Launch Readiness

> **Status**: ??Implementation Complete  
> **Date**: 2026-01-05  
> **Goal**: ?덉쟾???좊즺 ?곗묶???꾪븳 理쒖냼 ?꾩닔 湲곕뒫 援ы쁽

---

## ?뱥 援ы쁽 ?꾨즺 ??ぉ

### ??1. Stripe Webhook Idempotency (CRITICAL)
**?뚯씪**:
- `alembic/versions/2026_01_05_p0_stripe_idempotency.py`
- `app/models/stripe_event.py`
- `app/routers/webhooks.py` (Stripe webhook ?몃뱾??異붽?)

**?듭떖 湲곕뒫**:
- `stripe_events` ?뚯씠釉??앹꽦 (`event_id` UNIQUE ?쒖빟議곌굔)
- INSERT ?쒕룄 ??IntegrityError 罹먯튂濡?以묐났 諛⑹?
- ?숈씪 webhook 5???꾩넚 ??DB ?덉퐫??1媛쒕쭔 ?앹꽦

**寃利?諛⑸쾿**:
```bash
# ?뚯뒪???ㅽ뻾
pytest tests/test_p0_webhook_idempotency.py::test_webhook_idempotency_five_duplicates -v

# ?덉긽 寃곌낵: PASSED (1 event in DB)
```

---

### ??2. Subscription Access State
**?뚯씪**:
- `app/models/subscription.py` (`access_state` ?꾨뱶 異붽?)

**?듭떖 湲곕뒫**:
- Stripe status? 遺꾨━???대? ?곹깭 愿由?
- Values: `'active'`, `'warning'`, `'suspended'`
- `is_active` property: `access_state == 'active'`

**WHY**: Stripe webhook 吏???놁씠 利됱떆 ?묎렐 ?쒖뼱 媛??

---

### ??3. Dunning Recovery
**?뚯씪**:
- `app/services/dunning_service.py`
- `app/routers/webhooks.py` (payment_failed/succeeded ?몃뱾??
- `frontend/src/components/DunningBanner.tsx`

**?듭떖 ?뚮줈??*:
1. `invoice.payment_failed` ??`access_state = 'warning'` (利됱떆 ?대찓??
2. 7??寃쎄낵 ??`access_state = 'suspended'` (daily job)
3. `invoice.payment_succeeded` ??`access_state = 'active'` (利됱떆 蹂듦뎄)

**寃利?諛⑸쾿**:
```bash
# Dunning flow ?뚯뒪??
pytest tests/test_p0_webhook_idempotency.py::test_dunning_flow_payment_failed_to_recovered -v
```

---

### ??4. Event Tracking (Server-Side)
**?뚯씪**:
- `alembic/versions/2026_01_05_p0_analytics_events.py`
- `app/models/analytics_event.py`
- `app/services/analytics_service.py`

**?듭떖 ?대깽??(P0 8媛?**:
1. `user_signed_up`
2. `user_logged_in`
3. `trial_started`
4. `onboarding_step_completed`
5. `audit_completed`
6. `content_generated`
7. `subscription_created`
8. `payment_failed` / `payment_recovered`

**?ъ슜 ?덉떆**:
```python
from app.services.analytics_service import track_event

track_event(
    user_id=user.id,
    event_name="audit_completed",
    properties={"location_id": location.id, "score": 85},
    account_id=account.id,
    db=db
)
```

---

### ??5. Onboarding Checklist
**?뚯씪**:
- `alembic/versions/2026_01_05_p0_onboarding_ai_costs.py`
- `app/models/onboarding.py` (`OnboardingProgress` 異붽?)
- `app/services/onboarding_service.py`
- `app/routers/onboarding_progress.py`
- `frontend/src/components/OnboardingChecklist.tsx`

**4 Steps (?ㅼ젣 ?꾨즺 媛??**:
1. `run_audit` - Run first SEO audit
2. `view_insights` - View audit results
3. `generate_content` - Generate first AI content
4. `generate_social_card` - Generate first social proof card

**API ?붾뱶?ъ씤??*:
```
GET  /api/onboarding/progress
POST /api/onboarding/complete-step {"step": "run_audit"}
GET  /api/onboarding/time-to-activation
```

---

### ??6. AI Cost Monitoring
**?뚯씪**:
- `app/models/ai_cost.py`
- `app/services/ai_cost_service.py`

**鍮꾩슜 ?쒕룄 (?붾퀎)**:
- FREE: $0
- STARTER: $5
- PRO: $10
- PREMIUM: $20
- AGENCY: $50

**?ъ슜 ?덉떆**:
```python
from app.services.ai_cost_service import AiCostService
from decimal import Decimal

service = AiCostService(db)

# BEFORE API call: Check limit
estimated_cost = service.calculate_gemini_cost(input_tokens=1000, output_tokens=500)
service.check_cost_limit(user_id, account_id, estimated_cost)  # Raises 402 if exceeded

# AFTER API call: Record actual cost
service.record_cost(
    user_id=user_id,
    account_id=account_id,
    feature="competitor_analysis",
    api_provider="gemini",
    cost_usd=Decimal("0.035"),
    tokens_input=1000,
    tokens_output=500
)
```

---

## ?? 諛고룷 ?덉감

### Step 1: 留덉씠洹몃젅?댁뀡 ?ㅽ뻾
```bash
# 1. 留덉씠洹몃젅?댁뀡 ?뚯씪 ?뺤씤
ls alembic/versions/2026_01_05_*

# 2. 留덉씠洹몃젅?댁뀡 ?ㅽ뻾
alembic upgrade head

# 3. ?뺤씤
alembic current
```

### Step 2: ?섍꼍 蹂???ㅼ젙
`.env` ?뚯씪??異붽?:
```bash
# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Email (Dunning ?뚮┝??
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### Step 3: Stripe Webhook ?ㅼ젙
1. Stripe Dashboard ??Developers ??Webhooks
2. Add endpoint: `https://your-domain.com/webhooks/stripe`
3. Select events:
   - `invoice.payment_failed`
   - `invoice.payment_succeeded`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
4. Copy webhook secret ??`.env`??`STRIPE_WEBHOOK_SECRET`

### Step 4: Daily Job ?ㅼ젙 (Dunning Suspension)
```python
# app/jobs/dunning_check.py
from app.services.dunning_service import DunningService
from app.db.session import get_db

async def run_dunning_check():
    """Daily job: Suspend subscriptions overdue 7+ days"""
    db = next(get_db())
    service = DunningService(db)
    suspended_count = await service.suspend_overdue_subscriptions()
    print(f"Suspended {suspended_count} subscriptions")
    db.close()

# Cron: 留ㅼ씪 ?ㅼ쟾 9???ㅽ뻾
# 0 9 * * * cd /app && python -c "import asyncio; from app.jobs.dunning_check import run_dunning_check; asyncio.run(run_dunning_check())"
```

---

## ?㎦ ?뚯뒪???ㅽ뻾

### Webhook Idempotency ?뚯뒪??
```bash
pytest tests/test_p0_webhook_idempotency.py -v

# ?덉긽 寃곌낵:
# ??test_webhook_idempotency_duplicate_event PASSED
# ??test_webhook_idempotency_five_duplicates PASSED
# ??test_dunning_flow_payment_failed_to_recovered PASSED
```

### Smoke Tests (?섎룞)
```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Webhook endpoint
curl -X POST http://localhost:8000/webhooks/stripe \
  -H "Content-Type: application/json" \
  -H "stripe-signature: test" \
  -d '{"id":"evt_test","type":"ping","data":{}}'

# 3. Onboarding progress
curl http://localhost:8000/api/onboarding/progress \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## ?뱤 紐⑤땲?곕쭅

### 以묒슂 吏??
1. **Webhook 泥섎━??*
   ```sql
   SELECT 
     event_type,
     COUNT(*) as total,
     COUNT(DISTINCT event_id) as unique_events
   FROM stripe_events
   WHERE created_at >= NOW() - INTERVAL '24 hours'
   GROUP BY event_type;
   ```

2. **Dunning ?곹깭**
   ```sql
   SELECT 
     access_state,
     COUNT(*) as count
   FROM subscriptions
   GROUP BY access_state;
   ```

3. **AI 鍮꾩슜 (?붾퀎)**
   ```sql
   SELECT 
     DATE_TRUNC('month', created_at) as month,
     SUM(cost_usd) as total_cost
   FROM ai_usage_costs
   GROUP BY month
   ORDER BY month DESC;
   ```

4. **Onboarding ?꾨즺??*
   ```sql
   SELECT 
     COUNT(*) FILTER (WHERE completed_at IS NOT NULL) * 100.0 / COUNT(*) as completion_rate,
     AVG(EXTRACT(EPOCH FROM (completed_at - created_at))/60) as avg_time_minutes
   FROM onboarding_progress;
   ```

---

## ?슚 ?곗묶 ??泥댄겕由ъ뒪??

### CRITICAL (諛섎뱶???뺤씤)
- [ ] Stripe webhook secret ?ㅼ젙 ?꾨즺
- [ ] Webhook idempotency ?뚯뒪???듦낵
- [ ] Dunning flow ?뚯뒪???듦낵 (payment_failed ??warning ??recovered)
- [ ] AI cost cap ?뚯뒪??(?쒕룄 珥덇낵 ??402 ?먮윭)
- [ ] Daily dunning job ?ㅼ?以??ㅼ젙

### IMPORTANT (沅뚯옣)
- [ ] Sentry ?먮윭 紐⑤땲?곕쭅 ?ㅼ젙
- [ ] Stripe webhook ?ㅽ뙣 ?뚮┝ (Slack/Email)
- [ ] DB 諛깆뾽 ?먮룞??(daily)
- [ ] 濡쒓렇 ?덈꺼 ?뺤씤 (INFO ?댁긽)

### NICE TO HAVE
- [ ] Grafana ??쒕낫??(webhook 泥섎━?? dunning ?곹깭)
- [ ] 二쇨컙 由ы룷??(AI 鍮꾩슜, onboarding ?꾨즺??

---

## ?맀 ?몃윭釉붿뒋??

### 1. Webhook 以묐났 泥섎━
**利앹긽**: ?숈씪 event_id媛 ?щ윭 踰?泥섎━?? 
**?먯씤**: IntegrityError 罹먯튂 ?ㅽ뙣  
**?닿껐**:
```python
# stripe_events ?뚯씠釉붿뿉 UNIQUE ?쒖빟議곌굔 ?뺤씤
SELECT constraint_name, constraint_type 
FROM information_schema.table_constraints 
WHERE table_name = 'stripe_events' AND constraint_type = 'UNIQUE';
```

### 2. Dunning ?대찓??諛쒖넚 ?ㅽ뙣
**利앹긽**: payment_failed ?대깽??泥섎━?섏?留??대찓????媛? 
**?먯씤**: SMTP ?ㅼ젙 ?ㅻ쪟  
**?닿껐**:
```bash
# .env ?뺤씤
echo $SMTP_HOST
echo $SMTP_USER

# ?뚯뒪???대찓??諛쒖넚
python -c "from app.services.email_service import EmailService; import asyncio; asyncio.run(EmailService().send_email('test@example.com', 'Test', 'Test body'))"
```

### 3. AI Cost Cap 誘몄옉??
**利앹긽**: ?쒕룄 珥덇낵?대룄 API ?몄텧 媛?? 
**?먯씤**: `check_cost_limit()` ?몄텧 ?꾨씫  
**?닿껐**: 紐⑤뱺 AI API ?몄텧 ?꾩뿉 諛섎뱶???몄텧
```python
# ??WRONG
result = await gemini_api.generate(prompt)

# ??CORRECT
service.check_cost_limit(user_id, account_id, estimated_cost)
result = await gemini_api.generate(prompt)
service.record_cost(user_id, account_id, "feature", "gemini", actual_cost)
```

---

## ?뱷 ?ㅼ쓬 ?④퀎 (P1)

P0 ?꾨즺 ???ㅼ쓬 ?곗꽑?쒖쐞:
1. **Referral MVP** (2?? - ?щ젅??湲곕컲, ?대럭吏?諛⑹?
2. **Contextual Upsell** (1?? - 3媛吏 ?몃━嫄?
3. **Retention Email** (2?? - ?⑤낫??誘몄셿猷? ?щ갑臾??좊룄
4. **AI 湲곕뒫 ?ㅼ?以꾨쭅** (3?? - ??+ 由ы듃?쇱씠

---

## ?렞 ?깃났 吏??(P0 ?꾨즺 湲곗?)

- ??Webhook idempotency ?뚯뒪??100% ?듦낵
- ??Dunning flow ?뚯뒪??100% ?듦낵
- ??AI cost cap ?뚯뒪??100% ?듦낵
- ??Onboarding progress ?몃옒???묐룞
- ???꾨줈?뺤뀡 諛고룷 ??24?쒓컙 臾댁궗怨?

**?꾩옱 ?곹깭**: ?윟 **READY FOR DEPLOYMENT**

