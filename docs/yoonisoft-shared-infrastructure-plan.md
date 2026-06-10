# 공유 인프라 전략

마지막 업데이트: 2026-05-03

## 결론

인프라는 일부 같이 쓰는 것이 맞습니다. 특히 초기에는 비용 절감을 위해 `계정`, `DNS`, `정적 호스팅`, `로그/모니터링`, `이메일 인증 기반`, `AI 사용 정책`, `공통 운영 문서`를 묶는 것이 좋습니다.

다만 모든 SaaS를 하나의 서버, 하나의 DB, 하나의 발신 도메인, 하나의 worker에 억지로 합치면 비용은 잠깐 줄어도 장애 범위, 보안, compliance, 제품별 실험 속도에서 손해가 커질 수 있습니다.

따라서 추천 구조는 **공유 운영 계층 + 제품별 런타임 분리**입니다.

## 현재 확정된 공통 자산

| 항목 | 상태 | 원칙 |
| --- | --- | --- |
| 대표 도메인 | `yoonisoft.com` 보유 | Yooni Soft 회사 사이트와 공통 subdomain 관리 기준 |
| 대표 메일 | Google Workspace `admin@yoonisoft.com` 생성 완료 | 계정 등록, 운영 알림, 초기 관리 메일 |
| Stripe | 차주 등록 예정 | Yooni Soft 계정 1개, 제품별 product/price/webhook 분리 |
| AI provider | 제품별 key 분리 예정 | billing은 총괄하되 key, budget, usage tag는 제품별 분리 |
| 모니터링 | 중앙 총괄 도구 개발 필요 | 한 화면에서 전체 프로젝트 health, 비용 위험, backup 상태 확인 |
| 백업 정책 | 공통 정책 작성 및 배포 | 제품별 DB는 분리, retention/restore drill은 공통 기준 적용 |

## 공유하면 좋은 것

| 영역 | 공유 방식 | 비용 절감 효과 | 주의점 |
| --- | --- | --- | --- |
| DNS/도메인 관리 | Cloudflare 같은 한 계정에서 Yooni Soft 관련 domain 관리 | DNS 관리와 SSL 설정 단순화 | 제품별 subdomain은 분리 |
| 정적 사이트 호스팅 | Yooni Soft site, LoveKorea, product landing page를 정적 hosting에 배치 | 서버 비용 거의 없음 | SaaS app과 landing page를 분리하면 좋음 |
| 이메일 인증 기반 | SPF/DKIM/DMARC 정책과 발신 도메인 운영 원칙 통합 | 설정 중복 감소, deliverability 관리 쉬움 | 제품별 발신 subdomain은 분리해야 함 |
| Stripe 계정 | Yooni Soft 명의의 Stripe 계정에서 product/price를 제품별로 구분 | 결제 계정 관리 단순화 | webhook endpoint와 product metadata는 제품별 분리 |
| AI provider 계정 | OpenAI/Gemini 계정은 통합하고 project/key를 제품별 분리 | 결제와 사용량 추적 단순화 | key는 절대 공유하지 말고 제품별 budget/tag 필요 |
| 모니터링/알림 | 공통 Slack/이메일 alert 채널, 공통 incident rule | 유료 observability 도입 전 운영 부담 감소 | 고객 data가 alert에 노출되지 않게 주의 |
| 백업 정책 | Postgres backup retention, restore drill 문서 표준화 | 운영 실수 감소 | DB 자체는 제품별 분리 권장 |
| 공통 launch checklist | SaaS별 staging/production gate 표준화 | 반복 작업 감소 | 제품별 compliance 항목은 별도 유지 |

## 분리해야 하는 것

| 영역 | 분리 권장 이유 |
| --- | --- |
| Production DB | 한 제품 장애나 schema migration이 다른 제품을 망가뜨리면 안 됩니다. 제품별 고객 data도 분리하는 편이 안전합니다. |
| 환경 변수와 secret | key 하나가 유출되었을 때 전체 포트폴리오가 위험해지면 안 됩니다. |
| Email 발신 identity | `DraftSite AI`나 `PermitSignal AI`처럼 outbound 성격이 강한 제품은 domain reputation 리스크가 큽니다. |
| Worker/스케줄러 | 한 제품의 batch 작업이 다른 제품의 latency나 비용을 밀어 올리면 안 됩니다. |
| Admin 인증 | 제품별 권한, 고객, 운영자가 다릅니다. 공통 SSO는 나중 문제이고 초기에는 제품별 보호가 안전합니다. |
| Compliance log | outbound sales, permit intelligence, church data는 규칙이 다르므로 log와 audit trail을 섞지 않는 것이 좋습니다. |

## 추천 아키텍처

### 1단계: 아주 저렴한 공통 운영 기반

초기에는 다음만 공통으로 묶습니다.

- `yoonisoft.com` 중심 DNS/subdomain 관리
- Google Workspace `admin@yoonisoft.com` 중심 운영 메일
- Yooni Soft 공통 email domain 정책
- Stripe 계정 1개, 제품별 product/price 분리
- AI provider billing 계정 총괄, 제품별 API key 분리
- 공통 비용 ledger
- 공통 launch checklist
- 공통 backup/restore drill 정책
- 중앙 monitoring dashboard
- 정적 사이트는 Netlify/Cloudflare Pages/GitHub Pages 같은 저비용 hosting 사용

이 단계에서는 SaaS production runtime을 공유하지 않습니다.

### 2단계: 선택된 SaaS 1개만 staging

첫 후보는 `PermitSignal AI`입니다.

권장 구조:

- Railway project 1개
- Railway Postgres 1개
- test Stripe
- dry-run email
- mock AI 또는 낮은 사용량의 AI
- 제품 전용 env vars

이 단계에서 `Local SEO`, `Church`, `DraftSite`는 local/dry-run 상태를 유지합니다.

### 3단계: 공유 Platform을 만들지 말고, 공유 운영 규칙을 먼저 만든다

초기에는 monorepo 통합이나 공통 backend 플랫폼을 만들지 않습니다. 대신 다음을 표준화합니다.

- env var naming
- healthcheck
- admin lock
- billing webhook idempotency
- email dry-run mode
- suppression list 규칙
- AI budget cap
- backup/restore checklist
- staging smoke test

이렇게 하면 비용은 줄이고, 제품별 독립성은 유지할 수 있습니다.

### 4단계: 매출이 생긴 뒤 일부 공통화

반복 매출이 생기면 그때 다음을 검토합니다.

- 공통 auth/SSO
- 공통 billing dashboard
- 공통 email compliance service
- 공통 AI usage gateway
- 공통 admin observability dashboard
- 공통 customer support inbox

이 단계 전에는 공통 플랫폼을 만들기보다 각 제품을 빠르게 검증하는 편이 유리합니다.

## 제품별 공유 가능성

### Yooni Soft 회사 사이트 + LoveKorea 블로그

같이 묶기 좋습니다.

- 둘 다 정적 사이트입니다.
- 같은 DNS/hosting provider에서 관리해도 됩니다.
- 단, domain과 analytics property는 분리하는 편이 분석에 좋습니다.

### PermitSignal AI + DraftSite AI

운영 규칙은 공유하되, runtime은 분리하는 편이 좋습니다.

공유 가능:

- outbound email compliance 원칙
- suppression list 설계 패턴
- dry-run email adapter 패턴
- AI prompt/cost cap 정책

분리 권장:

- lead source
- 발신 subdomain
- campaign DB
- unsubscribe endpoint
- worker runtime

### Local SEO Optimizer + Church Platform

일부 SaaS 운영 패턴은 공유할 수 있지만, 제품 성격이 달라 runtime 통합은 추천하지 않습니다.

공유 가능:

- Stripe 운영 원칙
- Postgres backup/restore runbook
- admin access hardening
- Cloud Run 또는 GCP 배포 checklist

분리 권장:

- DB
- 고객 계정 모델
- domain control plane
- worker
- 알림/문자/이메일 provider 설정

## 비용을 줄이는 실제 방법

1. 정적 site와 product landing page는 SaaS app에서 분리해 static hosting에 둡니다.
2. SaaS staging은 한 번에 하나만 켭니다.
3. 모든 제품의 기본 email mode는 `dry_run`입니다.
4. 모든 제품의 기본 AI mode는 `mock` 또는 낮은 tier입니다.
5. worker는 상시 실행 대신 scheduled job, on-demand job, 또는 min instance 0을 우선합니다.
6. DB는 제품별로 분리하되, active staging DB 수를 제한합니다.
7. Stripe는 계정을 공유하되 webhook endpoint는 제품별로 분리합니다.
8. OpenAI/Gemini는 billing 계정을 공유하되 API key와 budget은 제품별로 분리합니다.
9. 로그는 platform 기본 로그부터 시작하고, paid observability는 유료 pilot 이후로 미룹니다.
10. 매월 "켜져 있는 것" 목록을 보고 사용하지 않는 service를 끕니다.

## 추천 도메인 구조 예시

| 용도 | 예시 |
| --- | --- |
| 회사 사이트 | `yoonisoft.com` |
| Local SEO 제품 | `localseo.yoonisoft.com` 또는 별도 브랜드 domain |
| Church 제품 | `church.yoonisoft.com` 또는 별도 브랜드 domain |
| PermitSignal | `permitsignal.yoonisoft.com` 또는 `permitsignal.ai` |
| DraftSite | `draftsite.yoonisoft.com` 또는 별도 브랜드 domain |
| 발신 이메일 | `mail.yoonisoft.com`, `mail.permitsignal...`, `mail.draftsite...`처럼 제품별 subdomain |

발신 이메일은 같은 root domain을 무리하게 공유하지 않는 편이 안전합니다. 특히 영업성 outbound가 있는 제품은 별도 subdomain으로 reputation을 격리해야 합니다.

## 최종 권장안

지금은 **공유 계정/정책/문서/정적 hosting은 통합하고, production DB/runtime/worker/email 발신 identity는 분리**하는 구조가 가장 좋습니다.

즉, 비용을 줄이되 한 제품의 실험이나 장애가 전체 Yooni Soft 포트폴리오에 번지지 않게 해야 합니다.
