from app.models.onboarding import OnboardingAudit
from app.services.conversion import ConversionFunnelService
from app.services.onboarding import OnboardingAuditService


def test_onboarding_recommends_competitive_market_for_large_review_gap(db):
    audit = OnboardingAudit(
        business_name="High Ticket Roofing",
        address="123 Main St",
        review_count=12,
        competitor_avg_reviews=90,
        competition_score=40,
        total_score=45,
        review_score=35,
        activity_score=55,
        completeness_score=70,
    )

    OnboardingAuditService(db)._generate_recommendations(audit)

    assert audit.recommended_plan == "competitive_market"


def test_solution_pricing_uses_managed_pilot_packages():
    audit = OnboardingAudit(
        business_name="Local Plumbing",
        address="123 Main St",
        recommended_plan="calls_growth",
        total_score=52,
        review_count=15,
        competitor_avg_reviews=40,
    )

    pricing = ConversionFunnelService().generate_solution_presentation(audit)["pricing"]

    assert pricing["recommended_plan"] == "calls_growth"
    assert pricing["plan_name"] == "Calls Growth"
    assert pricing["price_monthly"] == 999
    assert pricing["setup_fee"] == 799
    assert pricing["sales_motion"] == "managed_3_month_pilot"


def test_solution_pricing_maps_legacy_plan_ids_to_public_packages():
    audit = OnboardingAudit(
        business_name="Legacy Audit",
        address="123 Main St",
        recommended_plan="pro",
        total_score=42,
        review_count=10,
    )

    pricing = ConversionFunnelService().generate_solution_presentation(audit)["pricing"]

    assert pricing["recommended_plan"] == "calls_growth"
    assert pricing["plan_name"] == "Calls Growth"
