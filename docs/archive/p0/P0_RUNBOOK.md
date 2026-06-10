> [!WARNING]
> 이 문서는 legacy/참고용 문서입니다.
> 현재 구현 상태와 다를 수 있으므로, 사용 전 [docs/README.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/README.md), CODEBASE_ANALYSIS_KR_2026-03-06.md, EXECUTION_PRIORITY_ROADMAP_KR_2026-03-06.md, DEPLOYMENT_CHECKLIST.md를 먼저 확인하세요.
# P0 Operations Runbook

> **紐⑹쟻**: ?꾨줈?뺤뀡 ?댁쁺 以?諛쒖깮?섎뒗 ?댁뒋 ???媛?대뱶  
> **???*: DevOps, Backend Engineer, On-call Engineer

---

## ?슚 湲닿툒 ????쒕굹由ъ삤

### 1. Stripe Webhook ?ㅽ뙣 (CRITICAL)

**利앹긽**:
- Stripe Dashboard?먯꽌 webhook ?ㅽ뙣 ?쒖떆
- 寃곗젣 ?깃났?덉쑝??援щ룆 ?곹깭 ?낅뜲?댄듃 ?덈맖
- 怨좉컼??"寃곗젣?덈뒗???묎렐 ?덈맖" 臾몄쓽

**利됱떆 ?뺤씤**:
```sql
-- 理쒓렐 1?쒓컙 webhook ?대깽???뺤씤
SELECT event_id, event_type, created_at 
FROM stripe_events 
WHERE created_at >= NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC;

-- ?뱀젙 援щ룆??留덉?留??대깽???뺤씤
SELECT * FROM stripe_events 
WHERE payload->>'subscription' = 'sub_xxx'
ORDER BY created_at DESC LIMIT 5;
```

**蹂듦뎄 ?덉감**:
1. Stripe Dashboard ??Events ???ㅽ뙣???대깽??李얘린
2. ?대깽??ID 蹂듭궗 (?? `evt_xxx`)
3. ?섎룞 ?ъ쿂由?
```bash
# Admin endpoint濡??섎룞 replay (援ы쁽 ?꾩슂)
curl -X POST https://your-domain.com/admin/webhooks/replay \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"event_id": "evt_xxx"}'
```

**?덈갑**:
- Stripe webhook endpoint 紐⑤땲?곕쭅 (Uptime check)
- ?ㅽ뙣 ??Slack ?뚮┝ ?ㅼ젙
- 二쇨컙 由ы룷?? ?ㅽ뙣???뺤씤

---

### 2. Dunning ?대찓??諛쒖넚 ?ㅽ뙣

**利앹긽**:
- `payment_failed` ?대깽??泥섎━??
- `access_state = 'warning'` ?낅뜲?댄듃??
- ?섏?留??대찓??諛쒖넚 濡쒓렇 ?놁쓬

**利됱떆 ?뺤씤**:
```bash
# 濡쒓렇 ?뺤씤
grep "Dunning email sent" /var/log/app.log | tail -20
grep "Failed to send dunning email" /var/log/app.log | tail -20

# SMTP ?곌껐 ?뚯뒪??
telnet smtp.gmail.com 587
```

**蹂듦뎄 ?덉감**:
1. SMTP ?ㅼ젙 ?뺤씤:
```bash
echo $SMTP_HOST
echo $SMTP_PORT
echo $SMTP_USER
# SMTP_PASSWORD??蹂댁븞??異쒕젰 湲덉?
```

2. ?섎룞 ?대찓??諛쒖넚:
```python
# Python shell
from app.services.email_service import EmailService
from app.models.subscription import Subscription
from app.db.session import get_db
import asyncio

db = next(get_db())
subscription = db.query(Subscription).filter_by(id="sub_id_here").first()
service = EmailService()
asyncio.run(service.send_dunning_warning(subscription, attempt=1))
```

3. ????щ컻??(?꾩슂 ??:
```sql
-- ?대찓??誘몃컻??援щ룆 李얘린
SELECT s.id, s.account_id, a.user_id, u.email
FROM subscriptions s
JOIN accounts a ON s.account_id = a.id
JOIN users u ON a.user_id = u.id
WHERE s.access_state = 'warning'
  AND s.dunning_started_at >= NOW() - INTERVAL '24 hours'
  AND NOT EXISTS (
    SELECT 1 FROM email_logs 
    WHERE recipient = u.email 
      AND subject LIKE '%Payment Failed%'
      AND sent_at >= s.dunning_started_at
  );
```

---

### 3. AI 鍮꾩슜 ??＜ (CRITICAL)

**利앹긽**:
- ?쇱씪 AI 鍮꾩슜???덉긽移?珥덇낵 (?? $100 ??$1000)
- ?뱀젙 ?ъ슜?먯쓽 怨쇰룄??API ?몄텧

**利됱떆 ?뺤씤**:
```sql
-- ?ㅻ뒛 珥?鍮꾩슜
SELECT SUM(cost_usd) as total_cost
FROM ai_usage_costs
WHERE created_at >= CURRENT_DATE;

-- ?ъ슜?먮퀎 鍮꾩슜 (Top 10)
SELECT 
  user_id,
  SUM(cost_usd) as total_cost,
  COUNT(*) as api_calls
FROM ai_usage_costs
WHERE created_at >= CURRENT_DATE
GROUP BY user_id
ORDER BY total_cost DESC
LIMIT 10;

-- 湲곕뒫蹂?鍮꾩슜
SELECT 
  feature,
  api_provider,
  SUM(cost_usd) as total_cost,
  COUNT(*) as calls
FROM ai_usage_costs
WHERE created_at >= CURRENT_DATE
GROUP BY feature, api_provider
ORDER BY total_cost DESC;
```

**湲닿툒 李⑤떒**:
```sql
-- ?뱀젙 ?ъ슜???쇱떆 李⑤떒 (access_state 蹂寃?
UPDATE subscriptions
SET access_state = 'suspended'
WHERE account_id IN (
  SELECT account_id FROM ai_usage_costs
  WHERE created_at >= CURRENT_DATE
  GROUP BY account_id
  HAVING SUM(cost_usd) > 50
);

-- ?먮뒗 ?뱀젙 ?ъ슜?먮쭔
UPDATE subscriptions
SET access_state = 'suspended'
WHERE account_id = 'account_id_here';
```

**洹쇰낯 ?먯씤 遺꾩꽍**:
```sql
-- ?섏떖?ㅻ윭???⑦꽩 李얘린
SELECT 
  user_id,
  feature,
  COUNT(*) as calls,
  AVG(cost_usd) as avg_cost,
  MAX(cost_usd) as max_cost,
  MIN(created_at) as first_call,
  MAX(created_at) as last_call
FROM ai_usage_costs
WHERE created_at >= CURRENT_DATE
GROUP BY user_id, feature
HAVING COUNT(*) > 100  -- ?섎（ 100???댁긽
ORDER BY calls DESC;
```

**蹂듦뎄**:
1. 鍮꾩슜 ?쒕룄 媛뺥솕 (肄붾뱶 ?섏젙):
```python
# app/services/ai_cost_service.py
COST_CAPS = {
    PlanType.PRO: Decimal("5.00"),  # $10 ??$5濡??꾩떆 ?섑뼢
}
```

2. ?ъ슜???곕씫 ??蹂듦뎄:
```sql
UPDATE subscriptions
SET access_state = 'active'
WHERE account_id = 'account_id_here';
```

---

### 4. Subscription Access State 遺덉씪移?

**利앹긽**:
- Stripe?먯꽌??`active`?몃뜲 ?깆뿉?쒕뒗 `suspended`
- ?먮뒗 洹?諛섎?

**利됱떆 ?뺤씤**:
```sql
-- Stripe status vs access_state 遺덉씪移?李얘린
SELECT 
  id,
  stripe_subscription_id,
  status as stripe_status,
  access_state,
  dunning_started_at,
  updated_at
FROM subscriptions
WHERE status = 'active' AND access_state != 'active'
   OR status != 'active' AND access_state = 'active';
```

**蹂듦뎄 ?덉감**:
1. Stripe Dashboard?먯꽌 ?ㅼ젣 ?곹깭 ?뺤씤
2. ?섎룞 ?숆린??
```sql
-- Stripe媛 留욌떎硫?
UPDATE subscriptions
SET access_state = 'active',
    dunning_started_at = NULL,
    payment_retry_count = 0
WHERE stripe_subscription_id = 'sub_xxx';

-- ???곹깭媛 留욌떎硫?(Stripe ?낅뜲?댄듃 ?꾩슂)
-- Stripe API濡?援щ룆 痍⑥냼/?ш컻
```

3. 理쒓렐 webhook ?대깽???뺤씤:
```sql
SELECT * FROM stripe_events
WHERE payload->>'subscription' = 'sub_xxx'
ORDER BY created_at DESC LIMIT 10;
```

---

### 5. Onboarding Progress 珥덇린???붿껌

**利앹긽**:
- ?ъ슜?먭? "泥섏쓬遺???ㅼ떆 ?섍퀬 ?띕떎" ?붿껌
- ?먮뒗 ?뚯뒪??怨꾩젙 珥덇린???꾩슂

**蹂듦뎄 ?덉감**:
```sql
-- ?뱀젙 ?ъ슜??onboarding 珥덇린??
DELETE FROM onboarding_progress WHERE user_id = 'user_id_here';

-- ?먮뒗 由ъ뀑 (?꾨즺 ?곹깭 ?좎??섎㈃???ъ떆???덉슜)
UPDATE onboarding_progress
SET completed_steps = 0,
    current_step = 'run_audit',
    steps_data = '{}',
    completed_at = NULL
WHERE user_id = 'user_id_here';
```

---

## ?뱤 ?쇱씪 紐⑤땲?곕쭅 泥댄겕由ъ뒪??

### 留ㅼ씪 ?ㅼ쟾 9??(?먮룞??沅뚯옣)

1. **Webhook 泥섎━ ?곹깭**
```sql
SELECT 
  DATE(created_at) as date,
  event_type,
  COUNT(*) as total
FROM stripe_events
WHERE created_at >= CURRENT_DATE - INTERVAL '1 day'
GROUP BY DATE(created_at), event_type
ORDER BY date DESC, total DESC;
```

2. **Dunning ?곹깭**
```sql
SELECT 
  access_state,
  COUNT(*) as count,
  AVG(EXTRACT(EPOCH FROM (NOW() - dunning_started_at))/86400) as avg_days
FROM subscriptions
WHERE access_state IN ('warning', 'suspended')
GROUP BY access_state;
```

3. **AI 鍮꾩슜**
```sql
SELECT 
  DATE(created_at) as date,
  SUM(cost_usd) as total_cost
FROM ai_usage_costs
WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

4. **Onboarding ?꾨즺??*
```sql
SELECT 
  DATE(created_at) as signup_date,
  COUNT(*) as total_users,
  COUNT(*) FILTER (WHERE completed_at IS NOT NULL) as completed,
  ROUND(COUNT(*) FILTER (WHERE completed_at IS NOT NULL) * 100.0 / COUNT(*), 2) as completion_rate
FROM onboarding_progress
WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY signup_date DESC;
```

---

## ?뵩 ?좎?蹂댁닔 ?묒뾽

### 二쇨컙 ?묒뾽 (留ㅼ＜ ?붿슂??

1. **Stripe Events ?뺣━** (90???댁긽 ??젣)
```sql
DELETE FROM stripe_events
WHERE created_at < NOW() - INTERVAL '90 days';
```

2. **Analytics Events ?꾩뭅?대툕** (180???댁긽)
```sql
-- ?꾩뭅?대툕 ?뚯씠釉붾줈 ?대룞 (?좏깮?ы빆)
INSERT INTO analytics_events_archive
SELECT * FROM analytics_events
WHERE created_at < NOW() - INTERVAL '180 days';

DELETE FROM analytics_events
WHERE created_at < NOW() - INTERVAL '180 days';
```

3. **AI Cost 由ы룷???앹꽦**
```bash
python scripts/generate_weekly_cost_report.py
```

### ?붽컙 ?묒뾽 (留ㅼ썡 1??

1. **Usage 由ъ뀑 ?뺤씤**
```sql
-- ??珥?usage reset???뺤긽 ?묐룞?덈뒗吏 ?뺤씤
SELECT 
  user_id,
  feature,
  current_usage,
  usage_limit,
  reset_at
FROM usage_tracking
WHERE reset_at >= DATE_TRUNC('month', CURRENT_DATE);
```

2. **諛깆뾽 寃利?*
```bash
# 理쒓렐 諛깆뾽 蹂듦뎄 ?뚯뒪??(staging ?섍꼍)
pg_restore -d staging_db /backups/latest.dump
```

---

## ?뱸 ?먯뒪而щ젅?댁뀡

### Level 1: On-call Engineer
- Webhook ?ㅽ뙣 ???섎룞 replay
- ?대찓??諛쒖넚 ?ㅽ뙣 ??SMTP ?뺤씤
- ?쇰컲 ?ъ슜??臾몄쓽

### Level 2: Backend Lead
- AI 鍮꾩슜 ??＜ ??湲닿툒 李⑤떒
- Subscription ?곹깭 遺덉씪移????섎룞 ?숆린??
- DB ?깅뒫 ?댁뒋

### Level 3: CTO/Founder
- 蹂댁븞 ?ш퀬 (API key ?좎텧 ??
- ?洹쒕え ?쒕퉬???μ븷 (1?쒓컙 ?댁긽)
- 踰뺤쟻 ?댁뒋 (GDPR, ?섎텋 ?붿껌 ??

---

## ?뱷 濡쒓렇 ?꾩튂

```
/var/log/app.log              # ?좏뵆由ъ??댁뀡 濡쒓렇
/var/log/webhook.log           # Webhook ?꾩슜 濡쒓렇
/var/log/dunning.log           # Dunning ?묒뾽 濡쒓렇
/var/log/ai_cost.log           # AI 鍮꾩슜 紐⑤땲?곕쭅 濡쒓렇
```

**以묒슂 濡쒓렇 ?⑦꽩**:
```bash
# Webhook 以묐났
grep "Duplicate webhook event ignored" /var/log/webhook.log

# Dunning 吏꾩엯
grep "entered dunning WARNING state" /var/log/dunning.log

# AI 鍮꾩슜 ?쒕룄 珥덇낵
grep "AI cost limit exceeded" /var/log/ai_cost.log

# ?먮윭
grep "ERROR" /var/log/app.log | tail -50
```

---

## ?렞 SLA 紐⑺몴

- **Webhook 泥섎━**: 99.9% ?깃났瑜?
- **Dunning ?대찓??*: 5遺???諛쒖넚
- **AI Cost Cap**: 100% 李⑤떒 (珥덇낵 ?덉슜 0%)
- **Onboarding Progress**: 99.99% ?뺥솗??

**?꾩옱 ?곹깭**: ?윟 **OPERATIONAL**

