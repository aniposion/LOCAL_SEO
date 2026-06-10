# Yooni Soft 공통 백업 정책

마지막 업데이트: 2026-05-03

## 목적

Yooni Soft의 여러 프로젝트가 서로 다른 hosting, DB, worker 구조를 가지더라도 백업 기준은 공통으로 유지합니다. 목표는 비용을 과하게 늘리지 않으면서도, 실수·배포 장애·DB migration 실패·계정 문제·데이터 손상에 대응할 수 있게 만드는 것입니다.

## 기본 원칙

1. production 데이터는 제품별로 분리한다.
2. 백업 정책은 공통으로 관리하지만, 백업 파일과 restore 권한은 제품별로 분리한다.
3. 백업은 만드는 것보다 복구를 검증하는 것이 더 중요하다.
4. local 개발 DB는 production 백업으로 보지 않는다.
5. secret은 백업 문서나 repo에 저장하지 않는다.
6. 고객 데이터가 들어간 백업은 암호화하고 접근자를 최소화한다.
7. 비용을 줄이기 위해 staging 백업 retention은 짧게, production retention은 길게 둔다.

## 데이터 등급

| 등급 | 예시 | 백업 필요도 | 보관 기준 |
| --- | --- | --- | --- |
| 코드/문서 | Git repo, docs, migrations | 높음 | Git remote와 release tag |
| 설정 | env var 이름, deployment manifest | 높음 | secret 값 제외 후 repo/docs 보관 |
| Secret | API key, DB password, webhook secret | 매우 높음 | password manager 또는 cloud secret manager. repo 저장 금지 |
| Production DB | 고객, 결제 상태, 캠페인, 교회 운영 데이터 | 매우 높음 | 자동 snapshot + restore drill |
| Staging DB | 테스트 데이터, fixture | 중간 | 짧은 retention |
| 파일/업로드 | 이미지, report, generated site asset | 제품별 판단 | object storage versioning 또는 scheduled export |
| 로그 | audit log, billing webhook log, email event | 높음 | 제품별 retention과 privacy 기준 적용 |

## 공통 Retention 기준

초기 비용 절감형 기준:

| 환경 | DB 백업 | 파일 백업 | 로그 보관 | 복구 검증 |
| --- | --- | --- | --- | --- |
| Local | 필수 아님 | 필수 아님 | 필수 아님 | 필요 시 수동 |
| Staging | 3-7일 | 필요한 fixture만 | 7-14일 | 월 1회 또는 큰 배포 전 |
| Production 초기 | 7일 daily + 4주 weekly | 30일 또는 제품별 lifecycle | 30일 | 월 1회 |
| Production 유료 고객 증가 후 | 14-30일 daily + 8-12주 weekly | 60-90일 또는 법/계약 기준 | 90일 이상 검토 | 월 1회 + major release 전 |

## 제품별 정책

### Yooni Soft 회사 소개 사이트

- 데이터 성격: 정적 파일, 문서, 이미지
- 백업 방식: Git remote와 release zip 보관
- DB 백업: 없음
- 중요 기준: `yoonisoft.com` DNS 설정과 hosting 설정을 문서화

### LoveKorea 블로그

- 데이터 성격: Hugo content, static asset, generated public output
- 백업 방식: Git remote, content 폴더, static assets
- DB 백업: 없음
- 중요 기준: `content/`, `static/`, `assets/`, `hugo.toml`, `netlify.toml`이 remote에 있어야 함
- YOITZI 연결 전까지 commerce DB를 만들지 않음

### PermitSignal AI

- 데이터 성격: permit data, subscribers, reports, payments, prospects, campaign/suppression data
- 백업 방식: Railway Postgres snapshot/export, Prisma migration history, report artifact retention
- staging: 3-7일 DB retention
- production 초기: daily snapshot 7일 + weekly 4주
- 중요 기준: Stripe event와 fulfillment idempotency log는 반드시 보존
- suppression list와 unsubscribe 기록은 영업성 발송 보호를 위해 별도 중요 데이터로 취급

### DraftSite AI

- 데이터 성격: leads, private previews, email audit, suppression, customer/site records
- 백업 방식: Postgres dump/snapshot, generated preview metadata, audit log
- staging 전까지 local/dry-run 중심
- production 전환 시 suppression/unsubscribe/audit log를 최우선 백업 대상에 포함
- preview asset은 private/noindex/tokenized 원칙을 유지하며 보관 기간을 제한

### Local SEO Optimizer

- 데이터 성격: local business accounts, locations, content, reviews, billing, Twilio/call logs, uploads
- 백업 방식: Postgres snapshot, GCS/object storage lifecycle, Alembic migrations
- production 초기: daily DB snapshot 7일 + weekly 4주
- 중요 기준: 외부 publish 상태와 internal approval state가 어긋나지 않게 webhook/job log 보존
- Twilio/Google/Instagram 연동 token은 secret manager에 보관하고 repo 백업 금지

### Church Platform

- 데이터 성격: church organization, people/households, forms, events, volunteers, billing, communication, domain state
- 백업 방식: Postgres snapshot, SQL migration history, domain control state export
- production 초기: daily DB snapshot 7일 + weekly 4주
- 중요 기준: 교회 구성원/가정 데이터는 민감도가 높으므로 접근 권한을 최소화
- restore drill은 schema migration이 많은 시기에 특히 중요

## Restore Drill 기준

각 SaaS는 production 전환 전 최소 한 번 restore drill을 해야 합니다.

검증 항목:

1. 최신 backup 위치를 찾을 수 있는가
2. 새 DB에 restore할 수 있는가
3. migration 버전과 app build가 맞는가
4. healthcheck가 통과하는가
5. admin 화면 또는 status endpoint에서 핵심 count가 보이는가
6. email/SMS/live worker가 restore 검증 중 accidental send를 하지 않는가
7. Stripe webhook replay나 fulfillment 중복이 발생하지 않는가

## 백업 운영 체크리스트

매주:

- active production/staging DB 목록 확인
- 최근 backup 성공 시간 확인
- worker가 backup 중 DB lock 또는 비용 폭증을 만들지 않는지 확인

매월:

- restore drill 1개 제품 이상 수행
- 오래된 staging DB와 artifact 삭제
- secret rotation 필요 여부 확인
- 백업 비용 확인

큰 배포 전:

- DB migration 포함 여부 확인
- 배포 직전 snapshot 생성
- rollback app version 확인
- live worker/scheduler 일시 중지 필요 여부 판단

## 금지 사항

- 실제 `.env` 파일을 Git repo나 이 중앙 허브에 저장하지 않는다.
- production DB dump를 암호화 없이 로컬 폴더에 장기 보관하지 않는다.
- 고객 데이터가 포함된 backup을 다른 제품 개발 DB에 넣지 않는다.
- outbound email 제품의 suppression list를 삭제하거나 덮어쓰지 않는다.
- restore test 중 live email/SMS를 발송하지 않는다.

## 중앙 관리

이 문서의 원본은 `C:\Users\uesr\Documents\New project 5\docs\common-backup-policy.md`입니다. 각 프로젝트에는 복사본을 배포합니다. 정책이 바뀌면 중앙 문서를 먼저 수정한 뒤 각 프로젝트에 다시 배포합니다.
