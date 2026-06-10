# 상용화 손익분기점 시뮬레이션

작성일: 2026-03-27  
제품 포지셔닝: `사장님이 직접 챙기기 힘든 로컬 운영 업무를 대신 굴려주는 운영 SaaS`

## 1. 한 줄 결론
현재 가격 구조라면 `수익이 나는 SaaS`가 될 가능성은 충분하다.  
다만 전제는 `제한된 파일럿 -> 반복 개선 -> 확장` 순서다.  
지금 단계에서 가장 큰 리스크는 원가보다 `지원 부담`과 `운영 복구 비용`이다.

## 2. 전제

### 현재 플랜 가격
기준:
- [frontend/src/app/pricing/page.tsx](/C:/Users/uesr/CascadeProjects/local-seo-optimizer/frontend/src/app/pricing/page.tsx)

- Starter: `$99 / mo`
- Pro: `$149 / mo`
- Premium: `$249 / mo`
- Agency: `문의`

### 외부 비용 기준
아래 값은 2026-03-27 기준 공식 가격표를 참고했다.

- OpenAI API pricing:
  - GPT-5 mini input `$0.25 / 1M tokens`
  - GPT-5 mini output `$2.00 / 1M tokens`
  - GPT-4o mini input `$0.15 / 1M tokens`
  - GPT-4o mini output `$0.60 / 1M tokens`
  - 출처: https://platform.openai.com/pricing

- Twilio SMS / Voice pricing:
  - 미국 SMS outbound starts at `$0.0083`
  - carrier fee 별도
  - failed message fee `$0.001`
  - 미국 local voice number `+$1.15 / month`
  - 출처:
    - https://www.twilio.com/en-us/sms/pricing/usa
    - https://www.twilio.com/de-de/voice/pricing/ir

### 경쟁 가격 참고
- NiceJob Reviews `$75 / mo`, Pro `$125 / mo`
  - 출처: https://get.nicejob.com/products
- HighLevel `Starter $97`, `Agency Pro $497`
  - 출처: https://www.gohighlevel.com/pricing
- Podium / Birdeye는 공개 정가보다 견적형 비중이 큼
  - 출처:
    - https://www.podium.com/getpricing/retail
    - https://birdeye.com/pricing/

## 3. 비용 가정
아래는 공식 가격표와 현재 제품 구조를 기준으로 잡은 `보수적 가정`이다.  
정확한 회계 수치가 아니라 `손익 판단용 운영 가정`이다.

### 직접 원가(COGS) 가정

| 플랜 | 월 매출 | AI/토큰 | Twilio/SMS/Voice | 호스팅/저장소/로그 | 직접 원가 합계 | 기여이익 |
|---|---:|---:|---:|---:|---:|---:|
| Starter | $99 | $1.5 | $0.0 | $4.5 | $6 | $93 |
| Pro | $149 | $3.0 | $2.0 | $5.0 | $10 | $139 |
| Premium | $249 | $6.0 | $10.0 | $8.0 | $24 | $225 |

### 왜 이렇게 잡았는가
- Starter:
  - posts / review draft / KPI / reports 위주
  - 통신비가 거의 없음
- Pro:
  - Instagram, Q&A, SEO draft, scheduler 사용량 반영
- Premium:
  - missed call text back
  - review booster
  - advanced response automation
  - 실제 통신비가 가장 많이 들어감

## 4. 평균 고객당 기여이익 시뮬레이션

### 기본 믹스 가정
- Starter `35%`
- Pro `45%`
- Premium `20%`

### 계산
- 평균 매출(ARPA):
  - `0.35 * 99 + 0.45 * 149 + 0.20 * 249 = $151.5`
- 평균 직접 원가:
  - `0.35 * 6 + 0.45 * 10 + 0.20 * 24 = $11.4`
- 평균 기여이익:
  - `$151.5 - $11.4 = $140.1`

즉, 현재 가격 구조가 유지되면 고객 1명당 월 `약 $140`의 기여이익을 기대할 수 있다.

## 5. 손익분기점 시뮬레이션

### 시나리오 A. 대표 주도 파일럿 운영
월 고정비 가정:
- 대표 생활비/급여: `$8,000`
- 공용 툴/모니터링/클라우드 기본비: `$2,000`
- 외주/CS/기타 운영비: `$2,000`

합계:
- `$12,000 / month`

손익분기점:
- `$12,000 / $140.1 ≈ 86 customers`

### 시나리오 B. 작은 운영팀 유지
월 고정비 가정:
- 대표: `$8,000`
- 엔지니어 1명: `$8,000`
- 운영/CS part-time 또는 contractor: `$4,000`
- 공용 인프라/툴/기타: `$3,000`

합계:
- `$23,000 / month`

손익분기점:
- `$23,000 / $140.1 ≈ 165 customers`

### 시나리오 C. 공개 SaaS 확장 준비
월 고정비 가정:
- 대표: `$8,000`
- 엔지니어 2명: `$16,000`
- 운영/CS: `$6,000`
- 인프라/광고/툴/기타: `$5,000`

합계:
- `$35,000 / month`

손익분기점:
- `$35,000 / $140.1 ≈ 250 customers`

## 6. 고객 수별 월 기여이익 표

기준:
- 평균 기여이익 `$140.1 / customer / month`

| 고객 수 | 기여이익 총액 | 시나리오 A 순손익 | 시나리오 B 순손익 | 시나리오 C 순손익 |
|---:|---:|---:|---:|---:|
| 25 | $3,503 | -$8,497 | -$19,497 | -$31,497 |
| 50 | $7,005 | -$4,995 | -$15,995 | -$27,995 |
| 100 | $14,010 | +$2,010 | -$8,990 | -$20,990 |
| 150 | $21,015 | +$9,015 | -$1,985 | -$13,985 |
| 200 | $28,020 | +$16,020 | +$5,020 | -$6,980 |
| 250 | $35,025 | +$23,025 | +$12,025 | +$25 |

## 7. 민감도 분석

### 케이스 1. Premium 통신비가 예상보다 커질 때
Premium 직접 원가를 `$24 -> $36`으로 올리면:
- 평균 직접 원가: `약 $13.8`
- 평균 기여이익: `약 $137.7`

손익분기점은 약간만 나빠진다.
- 파일럿 운영: `약 87명`
- 작은 운영팀: `약 167명`
- 공개 확장 준비: `약 255명`

즉, 현재 구조는 `AI 원가`보다 `Twilio/지원비`에 더 민감하다.

### 케이스 2. 지원 부담이 고객당 월 $20 추가될 때
초기에는 온보딩/설정/복구 지원이 많아질 수 있다.  
고객당 추가 운영 부담을 `$20`으로 잡으면:

- 평균 기여이익: `$140.1 -> $120.1`

손익분기점:
- 파일럿 운영: `약 100명`
- 작은 운영팀: `약 192명`
- 공개 확장 준비: `약 292명`

이 경우 핵심 리스크는 원가가 아니라 `사람이 수작업으로 붙는 비용`이다.

## 8. 해석

### 수익 가능성이 높은 이유
- 가격대가 시장 바깥이 아니다
- AI 토큰 원가는 생각보다 낮다
- 로컬 비즈니스는 리뷰/전화/운영 자동화에 이미 비용을 쓰고 있다
- Premium과 add-on은 통신비를 포함해도 마진이 남는다

### 수익 가능성을 해치는 요인
- 지원/설정/복구를 너무 많이 수동으로 처리할 때
- Premium 고객의 SMS/voice usage를 고정가로 무제한처럼 운영할 때
- 베타 기능 기대치를 과하게 약속해 환불/이탈이 커질 때
- paid acquisition을 너무 일찍 태워 CAC 회수가 안 될 때

## 9. 상용화 전략 제안

### 지금 맞는 전략
1. `Starter / Pro / Premium`만 공개
2. `Agency`는 계속 문의형 유지
3. 제한 파일럿 `10~20 accounts`로 시작
4. 업종 1~2개에 집중
5. paid acquisition보다 founder-led sales와 referral 중심

### 지금 피해야 하는 전략
1. broad self-serve 공개
2. Agency를 정가형으로 먼저 판매
3. Premium에 usage-heavy 고객을 무차별 수용
4. 광고비를 먼저 크게 태우는 구조

## 10. 최종 판단
이 제품은 `수익 가능한 product`다.  
다만 수익 공식은 다음과 같다.

`좋은 가격`보다 `낮은 지원 부담 + 유지율 + usage 통제`가 더 중요하다.

지금 현실적인 목표는 이렇다.
- 1차 목표: `100 paid customers` 전후에서 founder-led 흑자 가능성 확인
- 2차 목표: `150~200 customers`에서 작은 운영팀 유지 가능성 확인
- 3차 목표: 그 다음에야 broad public SaaS로 확장 검토

## 11. 참고
이 문서의 숫자는 현재 코드와 공식 가격표를 기준으로 한 `운영 가정 시뮬레이션`이다.  
실제 손익 판단 전에는 아래를 반드시 같이 본다.

- [MONETIZATION_SUMMARY.md](./MONETIZATION_SUMMARY.md)
- [MONETIZATION_BLUEPRINT.md](./MONETIZATION_BLUEPRINT.md)
- [PRODUCT_COMMERCIALIZATION_CHECKLIST_KR_2026-03-27.md](./PRODUCT_COMMERCIALIZATION_CHECKLIST_KR_2026-03-27.md)
