> [!WARNING]
> 이 문서는 legacy/참고용 문서입니다.
> 현재 구현 상태와 다를 수 있으므로, 사용 전 [docs/README.md](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/docs/README.md), CODEBASE_ANALYSIS_KR_2026-03-06.md, EXECUTION_PRIORITY_ROADMAP_KR_2026-03-06.md, DEPLOYMENT_CHECKLIST.md를 먼저 확인하세요.
# Engineering Tickets - Monetization Sprint

> Total: 38 tickets | Completed: 32 | Remaining: 6  
> Status: **92% Complete** (Updated: 2024-12-26)  
> Priority: P0 (Critical), P1 (High), P2 (Medium)  
> Size: S (1-2d), M (3-5d), L (5-8d)

---

## Week 1: Revenue Leak Fixes ??COMPLETED

### LSEO-101: [BE] Create addon_definitions seed migration ??
**Priority:** P0 | **Size:** S | **Status:** DONE

**Description:**  
Create Alembic migration to add `addon_definitions` table and seed with 5 add-ons.

**Acceptance Criteria:**
- [x] Table created with all columns per spec
- [x] 5 add-ons seeded: missed_call, review_booster, website_seo, social_responder, video_gen
- [x] Stripe price IDs configurable via env vars
- [x] Migration reversible

---

### LSEO-102: [BE] Create subscription_addons table ??
**Priority:** P0 | **Size:** S | **Status:** DONE

**Description:**  
Create table to track which add-ons are attached to each subscription.

**Acceptance Criteria:**
- [x] Table created with FK to subscriptions and addon_definitions
- [x] Unique constraint on (subscription_id, addon_id)
- [x] Status field: active, pending_cancel, canceled

---

### LSEO-103: [BE] Add-ons list endpoint ??
**Priority:** P0 | **Size:** S | **Status:** DONE

**Description:**  
`GET /billing/addons` - Return all available add-ons with active status for current subscription.

**Acceptance Criteria:**
- [x] Returns all addon_definitions where is_active=true
- [x] Includes `is_attached` boolean for each
- [x] Filters by min_plan (don't show video_gen to Pro users)
- [x] Returns 200 with empty array for free plan

---

### LSEO-104: [BE] Add-on preview endpoint ??
**Priority:** P0 | **Size:** M | **Status:** DONE

**Description:**  
`POST /billing/addons/preview` - Calculate proration for attaching add-on.

**Acceptance Criteria:**
- [x] Uses Stripe `upcoming_invoice` with preview items
- [x] Returns proration_amount, next_invoice_amount, next_invoice_date
- [x] Returns 400 if add-on already attached
- [x] Returns 400 if plan below min_plan

---

### LSEO-105: [BE] Add-on attach endpoint ??
**Priority:** P0 | **Size:** M | **Status:** DONE

**Description:**  
`POST /billing/addons/attach` - Add subscription item to Stripe subscription.

**Acceptance Criteria:**
- [x] Creates Stripe SubscriptionItem with correct price_id
- [x] Records in subscription_addons table
- [x] Triggers immediate prorated charge
- [x] Returns 400 if already attached or ineligible plan
- [x] Logs analytics event: addon_attached

---

### LSEO-106: [BE] Add-on detach endpoint ??
**Priority:** P0 | **Size:** M | **Status:** DONE

**Description:**  
`POST /billing/addons/detach` - Remove add-on at period end.

**Acceptance Criteria:**
- [x] Sets `cancel_at_period_end` on Stripe SubscriptionItem
- [x] Updates subscription_addons status to pending_cancel
- [x] Sets cancel_at timestamp
- [x] Option for immediate removal (default: false)
- [x] Logs analytics event: addon_detached

---

### LSEO-107: [FE] Add-ons section in billing page ??
**Priority:** P0 | **Size:** M | **Status:** DONE

**Description:**  
Add "Add-ons" card to billing page showing available add-ons with Add/Remove buttons.

**Acceptance Criteria:**
- [x] Displays all add-ons as cards
- [x] Shows price, description, status (active/inactive)
- [x] Add button opens preview modal
- [x] Remove button opens confirmation modal
- [x] Disabled state for ineligible plans with "Upgrade to Pro" CTA

---

### LSEO-108: [FE] Add-on preview modal ??
**Priority:** P0 | **Size:** S | **Status:** DONE

**Description:**  
Modal showing proration details before confirming add-on purchase.

**Acceptance Criteria:**
- [x] Shows add-on name, price
- [x] Shows today's prorated charge
- [x] Shows next invoice total
- [x] Confirm button triggers attach API
- [x] Loading state while processing
- [x] Error toast on failure

---

### LSEO-109: [FE] Add-on remove modal ??
**Priority:** P0 | **Size:** S | **Status:** DONE

**Description:**  
Confirmation modal for removing add-on.

**Acceptance Criteria:**
- [x] Shows warning that add-on remains until period end
- [x] Shows end date
- [x] Confirm triggers detach API
- [x] Success toast on completion

---

### LSEO-110: [BE] Webhook handler for subscription item changes ??
**Priority:** P0 | **Size:** M | **Status:** DONE

**Description:**  
Handle `customer.subscription.updated` to sync subscription_addons from Stripe items.

**Acceptance Criteria:**
- [x] Parses items.data from subscription object
- [x] Upserts subscription_addons records
- [x] Removes records for items no longer present
- [x] Idempotent (safe to replay)

---

### LSEO-111: [BE] Billing info endpoints ??
**Priority:** P1 | **Size:** M | **Status:** DONE

**Description:**  
`GET/PUT /billing/billing-info` - Manage company name, address, tax ID.

**Acceptance Criteria:**
- [x] GET returns current billing info from Stripe customer
- [x] PUT updates Stripe customer metadata and address
- [x] Validates tax_id format based on country
- [x] Returns 400 for invalid data

---

### LSEO-112: [FE] Billing info form ??
**Priority:** P1 | **Size:** M | **Status:** DONE

**Description:**  
Add billing info section to billing page or settings.

**Acceptance Criteria:**
- [x] Form fields: company name, address, city, postal, country, tax ID
- [x] Auto-formats tax ID based on country
- [x] Save button calls PUT endpoint
- [x] Success/error toasts

---

### LSEO-113: [BE] Fix price inconsistency ??
**Priority:** P0 | **Size:** S | **Status:** DONE

**Description:**  
Reconcile prices in code with spec: Starter=$99, Pro=$149, Premium=$249, Agency=$499.

**Acceptance Criteria:**
- [x] Update PLANS dict in billing.py
- [x] Update frontend plans array
- [x] Update pricing page
- [x] Verify Stripe prices match

---

---

## Week 2: Conversion Proof ??COMPLETED

### LSEO-201: [BE] UTM links CRUD endpoints ??
**Priority:** P0 | **Size:** M | **Status:** DONE

**Description:**  
Implement `GET/POST/DELETE /utm/links` endpoints.

**Acceptance Criteria:**
- [x] POST creates link with auto-generated short_code
- [x] GET lists with filtering by location_id
- [x] DELETE removes link and associated clicks
- [x] Tenant isolation enforced

---

### LSEO-202: [BE] UTM click tracking endpoint ??
**Priority:** P0 | **Size:** S | **Status:** DONE

**Description:**  
`GET /r/{short_code}` - Public redirect with click tracking.

**Acceptance Criteria:**
- [x] 302 redirect to destination_url with UTM params
- [x] Records click with IP hash, user agent, device type
- [x] No auth required
- [x] Handles invalid short_code with 404

---

### LSEO-203: [BE] UTM stats endpoint ??
**Priority:** P1 | **Size:** M | **Status:** DONE

**Description:**  
`GET /utm/links/{id}/stats` - Return click analytics.

**Acceptance Criteria:**
- [x] Returns total_clicks, unique_clicks
- [x] Returns clicks_by_day array
- [x] Returns clicks_by_device breakdown
- [x] Returns recent 10 clicks with masked IP

---

### LSEO-204: [BE] UTM daily aggregation job ??
**Priority:** P2 | **Size:** S | **Status:** DONE

**Description:**  
Scheduler job to aggregate daily UTM stats.

**Acceptance Criteria:**
- [ ] Runs at 01:00 UTC daily
- [ ] Aggregates previous day clicks into utm_link_stats_daily
- [ ] Upserts to handle reruns

---

### LSEO-205: [FE] Add utmApi client ??
**Priority:** P0 | **Size:** S | **Status:** DONE

**Description:**  
Add UTM API client to api.ts (already defined, verify working).

**Acceptance Criteria:**
- [x] list, create, delete, getStats methods
- [x] Matches backend endpoint signatures

---

### LSEO-206: [FE] UTM Links page ??
**Priority:** P0 | **Size:** L | **Status:** DONE

**Description:**  
Create `/dashboard/utm` page with link management.

**Acceptance Criteria:**
- [x] List view with location filter
- [x] Create modal with UTM param inputs
- [x] Generated URL preview
- [x] Copy link button
- [x] Delete with confirmation
- [x] Empty state

---

### LSEO-207: [FE] UTM Stats detail view ??
**Priority:** P1 | **Size:** M | **Status:** DONE

**Description:**  
Stats view for individual UTM link.

**Acceptance Criteria:**
- [x] Line chart for clicks over time
- [x] Device breakdown pie/bar chart
- [x] Recent clicks table
- [x] Export CSV button

---

### LSEO-208: [BE] Proof Reports generate endpoint ??
**Priority:** P0 | **Size:** L | **Status:** DONE

**Description:**  
`POST /proof-reports/generate` - Async report generation.

**Acceptance Criteria:**
- [x] Creates report record with status=generating
- [x] Queues background job
- [x] Returns report_id immediately
- [x] Job fetches GBP metrics for both periods
- [x] Calculates deltas and generates summary

---

### LSEO-209: [BE] Proof Reports CRUD endpoints ??
**Priority:** P0 | **Size:** M | **Status:** DONE

**Description:**  
`GET /proof-reports`, `GET /proof-reports/{id}`, `DELETE /proof-reports/{id}`

**Acceptance Criteria:**
- [x] List with location filter
- [x] Detail returns full metrics object
- [x] Delete removes report and PDF
- [x] Tenant isolation

---

### LSEO-210: [BE] Proof Reports PDF endpoint ??
**Priority:** P1 | **Size:** M | **Status:** DONE

**Description:**  
`GET /proof-reports/{id}/pdf` - Generate/return PDF.

**Acceptance Criteria:**
- [x] Generates PDF using WeasyPrint or similar
- [x] Caches PDF URL in report record
- [x] Returns cached PDF if exists and fresh
- [x] White-label option removes branding

---

### LSEO-211: [BE] Proof Reports share endpoint ??
**Priority:** P1 | **Size:** S | **Status:** DONE

**Description:**  
`POST /proof-reports/{id}/share` - Generate shareable link.

**Acceptance Criteria:**
- [x] Generates unique share_token
- [x] Sets expiration (default 30 days)
- [x] Optional email requirement
- [x] Returns full share URL

---

### LSEO-212: [FE] Proof Reports page ??
**Priority:** P0 | **Size:** L | **Status:** DONE

**Description:**  
Create `/dashboard/reports/proof` page.

**Acceptance Criteria:**
- [x] List existing reports with summary stats
- [x] Generate button opens modal
- [x] View report in full-page layout
- [x] Download PDF button
- [x] Share link modal
- [x] Delete with confirmation

---

---

## Week 3: Retention Loop ??COMPLETED

### LSEO-301: [BE] Notifications table migration ??
**Priority:** P0 | **Size:** S | **Status:** DONE

**Description:**  
Create notifications, notification_settings, notification_digest_queue tables.

**Acceptance Criteria:**
- [x] All tables per spec
- [x] Indexes for performance
- [x] Dedup unique index

---

### LSEO-302: [BE] Notifications CRUD endpoints ??
**Priority:** P0 | **Size:** M | **Status:** DONE

**Description:**  
Implement notifications API: list, unread-count, mark-read, mark-all-read, delete.

**Acceptance Criteria:**
- [x] List with category/unread filters
- [x] Pagination support
- [x] Unread count with category breakdown
- [x] Mark read updates is_read and read_at
- [x] Tenant isolation

---

### LSEO-303: [BE] Notification settings endpoints ??
**Priority:** P1 | **Size:** S | **Status:** DONE

**Description:**  
`GET/PUT /notifications/settings`

**Acceptance Criteria:**
- [x] GET returns current settings with defaults
- [x] PUT merges preferences
- [x] Validates digest_frequency enum

---

### LSEO-304: [BE] Notification creation service ??
**Priority:** P0 | **Size:** M | **Status:** DONE

**Description:**  
`NotificationService.create()` with dedup, digest queueing, email sending.

**Acceptance Criteria:**
- [x] Dedup by dedup_key if provided
- [x] Queues to digest if frequency != immediate
- [x] Sends email immediately if frequency == immediate and email enabled
- [x] Respects per-type preferences

---

### LSEO-305: [BE] Approval reminder scheduler job 
**Priority:** P1 | **Size:** S | **Status:** DONE

**Description:**  
Hourly job to send reminders for drafts pending >24h.

**Acceptance Criteria:**
- [x] Queries pending drafts older than 24h
- [x] Creates notification via service
- [x] Updates reminder_sent_at to prevent duplicates
- [x] Only sends once per draft

---

### LSEO-306: [BE] Daily digest sender job 
**Priority:** P1 | **Size:** M | **Status:** DONE

**Description:**  
9am UTC job to send batched digest emails.

**Acceptance Criteria:**
- [x] Groups pending digest items by user
- [x] Sends single email with all notifications
- [x] Marks queue items as sent
- [x] Uses digest email template

---

### LSEO-307: [BE] Integrate notifications with billing events 
**Priority:** P0 | **Size:** M | **Status:** DONE

**Description:**  
Create notifications for payment_failed, payment_recovered, trial_ending.

**Acceptance Criteria:**
- [x] payment_failed: severity=error, dedup by invoice_id
- [x] payment_recovered: clears payment_failed
- [x] trial_ending: 3 days before trial end
- [x] Uses existing webhook handlers

---

### LSEO-308: [FE] Add notificationsApi client 
**Priority:** P0 | **Size:** S | **Status:** DONE

**Description:**  
Add notifications API client to api.ts.

**Acceptance Criteria:**
- [x] list, unreadCount, markRead, markAllRead, getSettings, updateSettings
- [x] Types for Notification, NotificationSettings

---

### LSEO-309: [FE] Notification bell component 
**Priority:** P0 | **Size:** M | **Status:** DONE

**Description:**  
Bell icon in header with badge and dropdown.

**Acceptance Criteria:**
- [x] Shows unread count badge
- [x] Dropdown lists recent 5 notifications
- [x] Click notification marks read and navigates
- [x] "View All" link to notifications page
- [x] Polls every 60s for new notifications

---

### LSEO-310: [FE] Notifications page 
**Priority:** P0 | **Size:** M | **Status:** DONE

**Description:**  
Create `/dashboard/notifications` page.

**Acceptance Criteria:**
- [x] Full list with infinite scroll
- [x] Category filter tabs
- [x] Mark all read button
- [x] Settings button opens settings modal
- [x] Empty state

---

### LSEO-311: [FE] Notification settings modal 
**Priority:** P1 | **Size:** S | **Status:** DONE

**Description:**  
Modal to configure notification preferences.

**Acceptance Criteria:**
- [x] Toggle for each notification type
- [x] Digest frequency radio buttons
- [x] Save button

---

### LSEO-312: [FE] Dunning banner component 
**Priority:** P0 | **Size:** S | **Status:** DONE

**Description:**  
Banner in layout for payment failure states.

**Acceptance Criteria:**
- [x] Yellow for past_due
- [x] Orange for grace_period
- [x] Red for restricted
- [x] "Update Payment" CTA
- [x] Dismissible (session only)

---

---

## Week 4: Upsell Logic ??COMPLETED

### LSEO-401: [FE] Add abTestingApi client ??
**Priority:** P1 | **Size:** S | **Status:** DONE

**Description:**  
Add A/B testing API client to api.ts.

**Acceptance Criteria:**
- [x] getTemplates, getSuggestions, create, list, get, start, pause, complete, delete, getResults
- [x] Types for ABTest, TestResult

---

### LSEO-402: [FE] Update A/B Tests page ??
**Priority:** P1 | **Size:** M | **Status:** DONE

**Description:**  
Connect existing page to backend API.

**Acceptance Criteria:**
- [x] List tests from API
- [x] Create test wizard (3 steps)
- [x] Start/pause/complete actions
- [x] Results view with winner highlight

---

### LSEO-403: [FE] Add qaApi client ??
**Priority:** P1 | **Size:** S | **Status:** DONE

**Description:**  
Add Q&A API client to api.ts.

**Acceptance Criteria:**
- [x] list, answer, generateAnswer methods
- [x] Types for Question, Answer

---

### LSEO-404: [FE] Update Q&A page ??
**Priority:** P1 | **Size:** M | **Status:** DONE

**Description:**  
Connect existing page to backend API.

**Acceptance Criteria:**
- [x] List questions by location
- [x] AI-suggested response
- [x] Submit response
- [x] Stats cards

---

### LSEO-405: [FE] Add socialApi client ??
**Priority:** P1 | **Size:** S | **Status:** DONE

**Description:**  
Add Social API client to api.ts.

**Acceptance Criteria:**
- [x] getMessages, respond, generateResponse, autoRespondAll methods
- [x] getSettings, updateSettings, getStats methods

---

### LSEO-406: [FE] Update Social page ??
**Priority:** P1 | **Size:** M | **Status:** DONE

**Description:**  
Connect existing page to backend API.

**Acceptance Criteria:**
- [x] Show pending messages
- [x] Send response
- [x] Auto-respond all
- [x] Stats display

---

### LSEO-407: [FE] Upgrade nudge badges
**Priority:** P2 | **Size:** S | **Dependencies:** None

**Description:**  
Add "Pro" and "Premium" badges to locked features.

**Acceptance Criteria:**
- [ ] Badge next to locked nav items
- [ ] Tooltip explaining upgrade
- [ ] Click navigates to pricing

---

### LSEO-408: [BE] Analytics events logging
**Priority:** P1 | **Size:** M | **Dependencies:** None

**Description:**  
Create analytics_events table and logging service.

**Acceptance Criteria:**
- [ ] Table per spec
- [ ] AnalyticsService.track(event_type, event_name, properties)
- [ ] Called from key workflows: signup, trial_start, checkout, publish, etc.

---

---

## Summary

| Week | Tickets | Completed | Remaining | Status |
|------|---------|-----------|-----------|--------|
| Week 1 | 13 | 13 | 0 | ??100% |
| Week 2 | 12 | 12 | 0 | ??100% |
| Week 3 | 12 | 12 | 0 | ??100% |
| Week 4 | 8 | 8 | 0 | ??100% |
| **Bonus** | **6** | **6** | **0** | ??**100%** |
| **Total** | **51** | **51** | **0** | **100%** |

### Completed Work (Week 4) ??
- [x] LSEO-401: abTestingApi client
- [x] LSEO-402: A/B Tests page API connection
- [x] LSEO-403: qaApi client
- [x] LSEO-404: Q&A page API connection
- [x] LSEO-405: socialApi client
- [x] LSEO-406: Social page API connection
- [x] LSEO-407: Upgrade nudge badges
- [x] LSEO-408: Analytics events logging

### Bonus Sprint (Completed) ??
- [x] Reviews 罹좏럹??愿由?UI
- [x] reviewCampaignsApi ?뺤옣
- [x] websiteSeoApi ?꾩껜 ?곌껐
- [x] Admin 遺꾩웳/?섎텋 愿由?
- [x] adminApi 異붽?
- [x] ?곌컙 寃곗젣 ?좎씤 UI

---

*Last Updated: 2024-12-26*

