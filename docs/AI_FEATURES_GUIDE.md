# AI Features Guide

Final baseline: current codebase / regression suite `79 passed`

## 1. Purpose
This document explains the current AI feature set in practical terms.
It is not a launch announcement. It should be read as an implementation-aware guide tied to the current product state.

## 2. Current AI feature groups

### 2.1 Competitor Analysis
Purpose:
- Discover nearby competitors
- Generate weekly competitive intelligence
- Surface keyword, rating, and threat insights

Current state:
- Backend exists
- Frontend exists
- Ownership and UUID alignment were corrected
- Still needs stronger real-world validation for data quality and Google Places behavior

### 2.2 Review Responder
Purpose:
- Generate AI-assisted review replies
- Route them through approval
- Publish after approval

Current state:
- Pending / approve / reject flow is connected
- Ownership checks are in place
- Regression tests cover the core approval flow
- Remaining risk is real GBP publishing validation in live environments

### 2.3 Social Proof
Purpose:
- Turn positive reviews into reusable social proof cards
- Support approval before usage

Current state:
- Core generation and pending flow exist
- Placeholder/garbled text issues were cleaned up
- UUID/ownership consistency was corrected
- Still needs stronger verification around real publishing and external asset reliability

### 2.4 Review Booster
Purpose:
- Send review requests by SMS/email
- Track request state
- Recover gracefully from failures

Current state:
- Campaigns, requests, opt-out, feedback, and ownership checks are connected
- Retry policy exists
- Manual requeue exists
- Operator notification on terminal failure exists
- Frontend exposes retry state and retry action

### 2.5 AI Content Support
Purpose:
- Generate suggestions and content drafts
- Move drafts through approval and publish flows

Current state:
- Suggestions and generate flows are connected
- Draft -> approval -> resend notification -> publish works
- Upload flow is connected
- Still needs more operational hardening around publish retries and channel-specific failure handling

## 3. Operational status summary

| Feature | Status | Notes |
|---|---|---|
| Competitor Analysis | Partial | Good base, more live validation needed |
| Review Responder | Operational for pilot | Core workflow and tests in place |
| Social Proof | Partial | Approval flow ready, publishing validation remains |
| Review Booster | Operational for pilot | Retry and operator recovery included |
| AI Content | Operational for pilot | Core create/approve/publish connected |

## 4. What is actually verified
The current regression baseline covers these adjacent areas:
- review responder
- social proof
- review booster
- content generation entry points
- jobs
- ownership boundaries
- Stripe/Twilio-adjacent operational flows

Baseline:
- `79 passed`
- warnings `0`

## 5. What is not fully proven yet
- Real publisher behavior against live platform accounts
- Full external OAuth recovery behavior in production-like environments
- End-to-end ROI validation against measured revenue systems
- Operator-facing audit and recovery experience polish

## 6. Recommended reading
- [AI_FEATURES_GUIDE_KR.md](./AI_FEATURES_GUIDE_KR.md)
- [FEATURE_MATRIX.md](./FEATURE_MATRIX.md)
- [CODEBASE_ANALYSIS_KR_2026-03-06.md](./CODEBASE_ANALYSIS_KR_2026-03-06.md)
- [CODE_IMPROVEMENT_CHECKLIST_KR_2026-03-06.md](./CODE_IMPROVEMENT_CHECKLIST_KR_2026-03-06.md)

## 7. Bottom line
The AI feature set is no longer a concept-only layer.
The core workflows now exist in code, in UI, and in regression coverage. The remaining work is mostly about live-ops validation, recovery paths, and polish rather than raw feature invention.
