"""Conversion funnel service for onboarding → solution → CTA flow."""

import logging
from typing import Any

from app.models.onboarding import OnboardingAudit, AuditGrade

logger = logging.getLogger(__name__)


class ConversionFunnelService:
    """
    Service for generating personalized solution presentations.
    
    온보딩 분석 결과를 기반으로 "개인화된 해결책"을 제시하여
    전환율(Conversion Rate)을 극대화한다.
    
    핵심 원칙:
    1. "당신의 문제는 이것입니다"
    2. "해결하는 가장 쉬운 방법은 이것입니다"
    3. "우리가 다 자동으로 해드립니다"
    """

    # 3-Step Solution Recipe
    SOLUTION_STEPS = [
        {
            "step": 1,
            "emoji": "🔧",
            "title_en": "Auto Content Generation",
            "title_ko": "자동 콘텐츠 생성",
            "subtitle_en": "Google Posts + Instagram",
            "subtitle_ko": "Google Posts + Instagram",
            "features_en": [
                "AI recommends weekly post topics for your industry & location",
                "One-click image & text generation",
                "Auto-upload after your approval",
            ],
            "features_ko": [
                "매주 AI가 업종·지역에 맞는 포스트 주제 추천",
                "클릭 한 번으로 이미지·본문 자동 생성",
                "승인하면 자동 업로드",
            ],
            "benefit_en": "Increased activity → Higher Google Maps visibility",
            "benefit_ko": "활동성 증가 → Google Maps 노출 상승",
        },
        {
            "step": 2,
            "emoji": "📝",
            "title_en": "Review Management Automation",
            "title_ko": "리뷰 관리 자동화",
            "subtitle_en": "Never miss a review",
            "subtitle_ko": "리뷰를 놓치지 마세요",
            "features_en": [
                "Instant notification when new review arrives",
                "AI suggests 3 response drafts",
                "One-click publish",
            ],
            "features_ko": [
                "새 리뷰 발생 → 즉시 알림",
                "AI가 3가지 답변 초안 제시",
                "버튼 클릭 → 자동 게시",
            ],
            "benefit_en": "Maintain ratings → Build trust → More customers",
            "benefit_ko": "평점 유지 → 신뢰도 상승 → 고객 방문 증가",
        },
        {
            "step": 3,
            "emoji": "📈",
            "title_en": "KPI Dashboard",
            "title_ko": "전화/길찾기 증가 추적",
            "subtitle_en": "Track what matters",
            "subtitle_ko": "중요한 지표만 추적",
            "features_en": [
                "Auto-collect weekly Calls / Directions / Bookings",
                "Compare your position vs competitors",
                "Personalized weekly recommendations",
            ],
            "features_ko": [
                "이번 주 Calls / Directions / Bookings 자동 수집",
                "경쟁사 대비 내 위치 분석",
                "\"다음 주 이렇게 하세요\" 맞춤 추천",
            ],
            "benefit_en": "No manual analysis needed → Focus on revenue",
            "benefit_ko": "사장님이 직접 분석할 필요 없음 → 매출에 집중",
        },
    ]

    # Value propositions
    VALUE_PROPS = {
        "time_saving": {
            "emoji": "⏰",
            "title_en": "You don't have to do it yourself",
            "title_ko": "당신이 직접 할 필요가 없습니다",
            "description_en": "Everything is automated. Save 10+ hours per week.",
            "description_ko": "모든 것이 자동화됩니다. 주당 10시간 이상 절약.",
        },
        "revenue_impact": {
            "emoji": "💰",
            "title_en": "Google Maps = Real Revenue",
            "title_ko": "Google Maps는 매출과 직결됩니다",
            "description_en": "Calls + Directions = Real customer actions that drive sales.",
            "description_ko": "전화 + 길찾기 = 실제 고객 행동 = 매출 증가",
        },
        "cost_saving": {
            "emoji": "💵",
            "title_en": "10x cheaper than agencies",
            "title_ko": "대행사보다 10배 저렴합니다",
            "description_en": "$2,000/mo agency → $149/mo with us. Save $22,212/year.",
            "description_ko": "월 $2,000 대행사 → 월 $149. 연간 $22,212 절약.",
        },
    }

    def generate_solution_presentation(
        self,
        audit: OnboardingAudit,
        language: str = "en",
    ) -> dict[str, Any]:
        """
        Generate personalized solution presentation based on audit results.
        
        This is the critical conversion step after onboarding analysis.
        """
        # 1. Opening statement
        opening = self._generate_opening_statement(audit, language)

        # 2. Problem summary (from audit)
        problems = self._extract_problems(audit, language)

        # 3. Solution steps (personalized)
        solutions = self._generate_personalized_solutions(audit, language)

        # 4. Value propositions
        value_props = self._get_value_propositions(language)

        # 5. Projected improvement scenario
        projection = self._generate_improvement_projection(audit, language)

        # 6. CTA
        cta = self._generate_cta(audit, language)

        return {
            "opening": opening,
            "problems": problems,
            "solutions": solutions,
            "value_propositions": value_props,
            "projection": projection,
            "cta": cta,
            "pricing": self._get_pricing_info(audit),
        }

    def _generate_opening_statement(
        self,
        audit: OnboardingAudit,
        language: str,
    ) -> dict[str, str]:
        """Generate the opening statement after analysis."""
        if language == "ko":
            return {
                "headline": "분석이 완료되었습니다",
                "message": f"현재 상태를 분석해보니, Google Maps 노출과 전화·길찾기 전환을 크게 개선할 수 있는 여지가 있습니다.",
                "solution_intro": "이 문제를 해결할 수 있는 가장 효율적인 방법은 바로 'Local SEO Optimizer'입니다.",
                "tagline": "Google Maps에서 더 많은 고객을 자동으로 데려오는 AI 엔진",
            }
        else:
            return {
                "headline": "Analysis Complete",
                "message": f"Based on our analysis, there's significant room to improve your Google Maps visibility and customer conversions.",
                "solution_intro": "The most efficient way to solve this is Local SEO Optimizer.",
                "tagline": "AI Engine that automatically brings more customers from Google Maps",
            }

    def _extract_problems(
        self,
        audit: OnboardingAudit,
        language: str,
    ) -> list[dict[str, Any]]:
        """Extract problems from audit results."""
        problems = []

        # Activity problem
        if audit.activity_score and audit.activity_score < 60:
            days = audit._days_since_post() if audit.latest_post_date else 45
            problems.append({
                "emoji": "🔴",
                "status": "danger",
                "title_en": f"No Google Posts in {days}+ days",
                "title_ko": f"최근 {days}일 동안 Google Posts 없음",
                "impact_en": "Low activity = Lower visibility in search",
                "impact_ko": "활동성 부족 = 검색 노출 감소",
            })

        # Review gap problem
        review_gap = 0
        if audit.competitor_avg_reviews:
            review_gap = int(audit.competitor_avg_reviews - audit.review_count)
        if review_gap > 0:
            problems.append({
                "emoji": "🔴",
                "status": "danger",
                "title_en": f"{review_gap} fewer reviews than competitors",
                "title_ko": f"경쟁사 대비 리뷰 수 {review_gap}개 부족",
                "impact_en": "Fewer reviews = Less trust = Lost customers",
                "impact_ko": "리뷰 부족 = 신뢰도 하락 = 고객 이탈",
            })

        # Completeness problem
        missing = audit._get_missing_info() if hasattr(audit, '_get_missing_info') else []
        if len(missing) > 2:
            problems.append({
                "emoji": "🟡",
                "status": "warning",
                "title_en": "Incomplete business profile",
                "title_ko": "비즈니스 프로필 정보 불완전",
                "impact_en": f"Missing: {', '.join(missing[:3])}",
                "impact_ko": f"누락: {', '.join(missing[:3])}",
            })

        # Low conversion potential
        if audit.total_score and audit.total_score < 70:
            problems.append({
                "emoji": "🟡",
                "status": "warning",
                "title_en": "Low conversion potential",
                "title_ko": "전화/길찾기 전환이 낮은 편",
                "impact_en": "Potential customers are going to competitors",
                "impact_ko": "잠재 고객이 경쟁사로 이동 중",
            })

        return problems

    def _generate_personalized_solutions(
        self,
        audit: OnboardingAudit,
        language: str,
    ) -> list[dict[str, Any]]:
        """Generate personalized solution steps based on audit."""
        solutions = []

        for step in self.SOLUTION_STEPS:
            solution = {
                "step": step["step"],
                "emoji": step["emoji"],
                "title": step[f"title_{language}"] if f"title_{language}" in step else step["title_en"],
                "subtitle": step[f"subtitle_{language}"] if f"subtitle_{language}" in step else step["subtitle_en"],
                "features": step[f"features_{language}"] if f"features_{language}" in step else step["features_en"],
                "benefit": step[f"benefit_{language}"] if f"benefit_{language}" in step else step["benefit_en"],
            }

            # Add personalized context based on audit
            if step["step"] == 1 and audit.activity_score and audit.activity_score < 60:
                solution["urgency"] = "high"
                solution["personalized_note"] = (
                    "Your activity score is low. This will have the biggest immediate impact."
                    if language == "en" else
                    "활동성 점수가 낮습니다. 이것이 가장 즉각적인 효과를 줄 것입니다."
                )

            if step["step"] == 2 and audit.review_count and audit.review_count < 50:
                solution["urgency"] = "high"
                solution["personalized_note"] = (
                    f"You have {audit.review_count} reviews. Let's grow this to 50+."
                    if language == "en" else
                    f"현재 {audit.review_count}개 리뷰가 있습니다. 50개 이상으로 늘려봅시다."
                )

            solutions.append(solution)

        return solutions

    def _get_value_propositions(self, language: str) -> list[dict[str, str]]:
        """Get value propositions in the specified language."""
        props = []
        for key, prop in self.VALUE_PROPS.items():
            props.append({
                "key": key,
                "emoji": prop["emoji"],
                "title": prop[f"title_{language}"] if f"title_{language}" in prop else prop["title_en"],
                "description": prop[f"description_{language}"] if f"description_{language}" in prop else prop["description_en"],
            })
        return props

    def _generate_improvement_projection(
        self,
        audit: OnboardingAudit,
        language: str,
    ) -> dict[str, Any]:
        """Generate projected improvement scenario."""
        # Calculate projections based on current state
        current_score = audit.total_score or 50
        review_gap = 0
        if audit.competitor_avg_reviews:
            review_gap = max(0, int(audit.competitor_avg_reviews - audit.review_count))

        # Projected improvements
        projected_calls_increase = min(30, max(10, int((100 - current_score) * 0.3)))
        projected_directions_increase = min(25, max(8, int((100 - current_score) * 0.25)))
        reviews_to_add = min(15, max(5, review_gap // 2))

        if language == "ko":
            return {
                "headline": "맞춤형 개선 시나리오",
                "timeframe": "이번 달 안에",
                "actions": [
                    f"리뷰 {reviews_to_add}개 늘리고",
                    "Google Posts 주 2회 업로드하면",
                ],
                "expected_results": {
                    "calls": f"전화 약 {projected_calls_increase}~{projected_calls_increase + 10}회 추가 발생 예상",
                    "directions": f"길찾기 약 {projected_directions_increase}~{projected_directions_increase + 8}회 증가 예상",
                },
                "automation_note": "Local SEO Optimizer가 모든 과정(생성→승인→업로드)을 자동 처리합니다.",
            }
        else:
            return {
                "headline": "Your Personalized Improvement Plan",
                "timeframe": "Within this month",
                "actions": [
                    f"Add {reviews_to_add} new reviews",
                    "Post 2x per week on Google",
                ],
                "expected_results": {
                    "calls": f"Expected {projected_calls_increase}-{projected_calls_increase + 10} additional calls",
                    "directions": f"Expected {projected_directions_increase}-{projected_directions_increase + 8} more directions",
                },
                "automation_note": "Local SEO Optimizer handles everything automatically (create → approve → upload).",
            }

    def _generate_cta(
        self,
        audit: OnboardingAudit,
        language: str,
    ) -> dict[str, Any]:
        """Generate the final CTA section."""
        # Calculate target improvements
        calls_target = 23  # Default target
        directions_target = 17

        if language == "ko":
            return {
                "headline": f"지난달 대비 전화 +{calls_target}%, 길찾기 +{directions_target}% 증가를 목표로 시작해보세요.",
                "subheadline": "Local SEO Optimizer가 아래를 자동으로 수행합니다:",
                "features": [
                    "✔ Google Posts 자동 생성 + 업로드",
                    "✔ 리뷰 자동 수집 + 답변",
                    "✔ 전화/길찾기 분석 리포트",
                    "✔ 맞춤형 콘텐츠 추천",
                ],
                "button_text": "시작하기 – 7일 무료 체험",
                "button_subtext": "신용카드 불필요 · 언제든 취소 가능",
                "trust_badges": [
                    "🔒 데이터 암호화",
                    "⭐ 500+ 비즈니스 사용 중",
                    "💬 24시간 지원",
                ],
            }
        else:
            return {
                "headline": f"Target +{calls_target}% calls and +{directions_target}% directions vs last month.",
                "subheadline": "Start with a free preview, then unlock paid workflows when you are ready:",
                "features": [
                    "Review your audit and dashboard",
                    "Check setup, connection, and reporting readiness",
                    "Choose a paid plan before using AI, SMS, publishing, or automation",
                    "Stay in control before anything goes live",
                ],
                "button_text": "Start 3-Day Free Preview",
                "button_subtext": "No credit card required. Paid features stay locked until you choose a plan.",
                "trust_badges": [
                    "Data encrypted",
                    "No paid automation during preview",
                    "Upgrade only when ready",
                ],
            }

    def _get_pricing_info(self, audit: OnboardingAudit) -> dict[str, Any]:
        """Get managed pilot pricing information for the public sales flow."""
        recommended_plan = audit.recommended_plan or "maps_starter"

        legacy_plan_map = {
            "starter": "maps_starter",
            "pro": "calls_growth",
            "premium": "calls_growth",
            "agency": "competitive_market",
        }
        recommended_plan = legacy_plan_map.get(recommended_plan, recommended_plan)

        plans = {
            "maps_starter": {
                "name": "Maps Starter",
                "price": 699,
                "setup_fee": 499,
                "agency_equivalent": 1299,
                "positioning": "Best for smaller service businesses in lower-competition markets.",
            },
            "calls_growth": {
                "name": "Calls Growth",
                "price": 999,
                "setup_fee": 799,
                "agency_equivalent": 2000,
                "positioning": "Best for lead-driven home service businesses that need more calls.",
            },
            "competitive_market": {
                "name": "Competitive Market",
                "price": 1499,
                "setup_fee": 1500,
                "agency_equivalent": 3000,
                "positioning": "Best for high-competition cities, high-ticket services, or multi-location operators.",
            },
        }

        plan = plans.get(recommended_plan, plans["maps_starter"])
        monthly_savings = plan["agency_equivalent"] - plan["price"]
        yearly_savings = monthly_savings * 12

        return {
            "recommended_plan": recommended_plan,
            "plan_name": plan["name"],
            "price_monthly": plan["price"],
            "setup_fee": plan["setup_fee"],
            "positioning": plan["positioning"],
            "sales_motion": "managed_3_month_pilot",
            "agency_equivalent": plan["agency_equivalent"],
            "monthly_savings": monthly_savings,
            "yearly_savings": yearly_savings,
            "savings_message_en": f"Save about ${monthly_savings}/month vs heavier agency retainers (${yearly_savings}/year)",
            "savings_message_ko": f"대행사 대비 월 ${monthly_savings} 절약 (연 ${yearly_savings})",
        }


class SolutionPresenter:
    """Helper class to format solution presentation for different outputs."""

    @staticmethod
    def to_html(presentation: dict[str, Any], language: str = "en") -> str:
        """Convert presentation to HTML for web display."""
        # This would generate HTML for the frontend
        # Simplified version for API response
        return f"""
        <div class="solution-presentation">
            <h1>{presentation['opening']['headline']}</h1>
            <p>{presentation['opening']['message']}</p>
            <p class="solution-intro">{presentation['opening']['solution_intro']}</p>
            
            <div class="problems">
                {''.join(f"<div class='problem {p['status']}'>{p['emoji']} {p['title']}</div>" for p in presentation['problems'])}
            </div>
            
            <div class="solutions">
                {''.join(f"<div class='solution-step'><h3>{s['emoji']} Step {s['step']}: {s['title']}</h3></div>" for s in presentation['solutions'])}
            </div>
            
            <div class="cta">
                <h2>{presentation['cta']['headline']}</h2>
                <button>{presentation['cta']['button_text']}</button>
            </div>
        </div>
        """

    @staticmethod
    def to_json_summary(presentation: dict[str, Any]) -> dict[str, Any]:
        """Convert to simplified JSON for mobile apps."""
        return {
            "headline": presentation["opening"]["headline"],
            "problem_count": len(presentation["problems"]),
            "solution_count": len(presentation["solutions"]),
            "cta_text": presentation["cta"]["button_text"],
            "recommended_plan": presentation["pricing"]["recommended_plan"],
            "monthly_price": presentation["pricing"]["price_monthly"],
        }
