"""Shared commercial plan limits."""

from __future__ import annotations

from app.models.subscription import PLAN_FEATURES, PlanType
from app.services.credits import PLAN_CREDITS, SUBSCRIPTION_PLAN_TO_CREDITS_TIER


SUPPORTED_COMMERCIAL_PLANS = (
    PlanType.FREE,
    PlanType.MAPS_STARTER,
    PlanType.CALLS_GROWTH,
    PlanType.COMPETITIVE_MARKET,
    PlanType.STARTER,
    PlanType.PRO,
    PlanType.PREMIUM,
    PlanType.AGENCY,
    PlanType.ENTERPRISE,
)


def get_plan_limits(plan_type: PlanType) -> dict[str, int]:
    """Return the shared commercial limits for a subscription plan."""
    feature_config = PLAN_FEATURES.get(plan_type, PLAN_FEATURES[PlanType.FREE])
    credit_tier = SUBSCRIPTION_PLAN_TO_CREDITS_TIER.get(
        plan_type,
        SUBSCRIPTION_PLAN_TO_CREDITS_TIER[PlanType.FREE],
    )
    credit_config = PLAN_CREDITS[credit_tier]
    return {
        "locations": int(feature_config.get("locations_limit", 1)),
        "posts_per_month": int(feature_config.get("posts_per_month", 0)),
        "api_calls_per_day": int(credit_config.get("api_calls_daily", 0)),
    }


PLAN_LIMITS_BY_PLAN = {
    plan_type: get_plan_limits(plan_type)
    for plan_type in SUPPORTED_COMMERCIAL_PLANS
}
