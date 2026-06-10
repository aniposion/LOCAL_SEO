"""Feature access control service."""

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.subscription import (
    ADDON_PRICES,
    FREE_PREVIEW_DAYS,
    PLAN_FEATURES,
    PLAN_PRICES,
    AddOnType,
    PlanType,
    Subscription,
)
from app.services.account_entitlements import resolve_account_entitlement


class FeatureAccessService:
    """Service for checking feature access based on subscription."""

    def __init__(self, db: Session):
        self.db = db

    def get_subscription(self, account_id: UUID) -> Subscription | None:
        """Get subscription for an account."""
        return (
            self.db.query(Subscription)
            .filter(Subscription.account_id == account_id)
            .order_by(Subscription.created_at.desc())
            .first()
        )

    def check_feature_access(
        self,
        account: Account,
        feature: str,
        raise_exception: bool = True,
    ) -> bool:
        """
        Check if account has access to a specific feature.

        Args:
            account: The account to check
            feature: Feature name to check
            raise_exception: If True, raises HTTPException when access denied

        Returns:
            True if access is granted, False otherwise
        """
        entitlement = resolve_account_entitlement(self.db, account.id)
        subscription = entitlement.subscription

        if subscription and subscription.is_active:
            has_access = subscription.has_feature(feature)
        else:
            has_access = PLAN_FEATURES[entitlement.plan_type].get(feature, False)

        if not has_access and raise_exception:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "feature_not_available",
                    "feature": feature,
                    "message": "Choose a paid plan or add-on to unlock this feature.",
                    "upgrade_url": "/dashboard/billing",
                },
            )

        return has_access

    def get_account_features(self, account: Account) -> dict[str, Any]:
        """Get all features available to an account."""
        entitlement = resolve_account_entitlement(self.db, account.id)
        subscription = entitlement.subscription

        if not subscription or not subscription.is_active:
            return {
                "plan": entitlement.plan_type.value,
                "status": subscription.status.value if subscription else entitlement.source,
                "is_trial": False,
                "trial_end": subscription.trial_end.isoformat() if subscription and subscription.trial_end else None,
                "features": PLAN_FEATURES[entitlement.plan_type],
                "active_addons": [],
                "monthly_price": PLAN_PRICES.get(entitlement.plan_type, 0),
                "legacy_fallback": entitlement.is_legacy_fallback,
            }

        return {
            "plan": subscription.plan_type.value,
            "status": subscription.status.value,
            "is_trial": subscription.is_trial,
            "trial_end": subscription.trial_end.isoformat() if subscription.trial_end else None,
            "features": subscription.get_features(),
            "active_addons": subscription.active_addons or [],
            "monthly_price": subscription.get_monthly_price(),
            "legacy_fallback": False,
            "current_period_end": subscription.current_period_end.isoformat()
            if subscription.current_period_end
            else None,
        }

    def get_upgrade_options(self, account: Account) -> dict[str, Any]:
        """Get available upgrade options for an account."""
        entitlement = resolve_account_entitlement(self.db, account.id)
        subscription = entitlement.subscription
        current_plan = entitlement.plan_type

        plan_order = [
            PlanType.FREE,
            PlanType.MAPS_STARTER,
            PlanType.CALLS_GROWTH,
            PlanType.COMPETITIVE_MARKET,
            PlanType.STARTER,
            PlanType.PRO,
            PlanType.PREMIUM,
            PlanType.AGENCY,
        ]
        current_index = plan_order.index(current_plan) if current_plan in plan_order else 0

        available_plans = []
        for plan in plan_order[current_index + 1 :]:
            available_plans.append(
                {
                    "plan": plan.value,
                    "price": PLAN_PRICES[plan],
                    "features": PLAN_FEATURES[plan],
                }
            )

        active_addons = subscription.active_addons if subscription else []
        available_addons = []

        for addon in AddOnType:
            if addon.value not in active_addons:
                feature_name = {
                    AddOnType.MISSED_CALL_TEXT_BACK: "missed_call_text_back",
                    AddOnType.REVIEW_BOOSTER: "review_booster",
                    AddOnType.WEBSITE_SEO: "website_seo_full",
                    AddOnType.SOCIAL_AUTO_RESPONDER: "social_auto_responder",
                    AddOnType.VIDEO_GENERATOR: "video_generator",
                }.get(addon)

                plan_features = PLAN_FEATURES.get(current_plan, {})
                if not plan_features.get(feature_name, False):
                    available_addons.append(
                        {
                            "addon": addon.value,
                            "name": _ADDON_COPY[addon]["name"],
                            "price": ADDON_PRICES[addon],
                        }
                    )

        return {
            "current_plan": current_plan.value,
            "available_plans": available_plans,
            "available_addons": available_addons,
        }


def require_feature(feature: str):
    """Decorator to require a specific feature for a route."""
    from functools import wraps

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            db = kwargs.get("db")
            current_user = kwargs.get("current_user")

            if db and current_user:
                service = FeatureAccessService(db)
                service.check_feature_access(current_user, feature)

            return await func(*args, **kwargs)

        return wrapper

    return decorator


_PLAN_COPY: dict[PlanType, dict[str, Any]] = {
    PlanType.MAPS_STARTER: {
        "name": "Maps Starter",
        "period": "month",
        "description": "Managed Google Maps foundation work for one local business.",
        "target": "Smaller home service and local businesses in lower-competition markets.",
        "setup_fee": 499,
        "sales_motion": "managed_3_month_pilot",
        "features": [
            {"name": "Google Business Profile cleanup", "included": True},
            {"name": "Category and service optimization", "included": True},
            {"name": "Review request link and QR code", "included": True},
            {"name": "Google Business Profile post workflow", "included": True},
            {"name": "Basic competitor check", "included": True},
            {"name": "Simple monthly report", "included": True},
        ],
        "cta": "Start With a Free Audit",
        "popular": False,
    },
    PlanType.CALLS_GROWTH: {
        "name": "Calls Growth",
        "period": "month",
        "description": "Managed review, ranking, and local-page work for demand-driven teams.",
        "target": "Plumbers, HVAC teams, roofers, med spas, clinics, and appointment-heavy services.",
        "badge": "Most common starting point",
        "setup_fee": 799,
        "sales_motion": "managed_3_month_pilot",
        "features": [
            {"name": "Everything in Maps Starter", "included": True},
            {"name": "Local rank grid tracking", "included": True},
            {"name": "Review request SMS and email workflow", "included": True},
            {"name": "Review reply drafts", "included": True},
            {"name": "Local landing page workflow", "included": True},
            {"name": "Competitor review gap report", "included": True},
            {"name": "Monthly strategy call", "included": True},
        ],
        "cta": "Start With a Free Audit",
        "popular": True,
    },
    PlanType.COMPETITIVE_MARKET: {
        "name": "Competitive Market",
        "period": "month",
        "description": "Managed local growth operations for competitive cities and multi-location teams.",
        "target": "High-competition cities, higher-ticket services, or multi-location operators.",
        "setup_fee": 1500,
        "sales_motion": "managed_3_month_pilot",
        "features": [
            {"name": "Everything in Calls Growth", "included": True},
            {"name": "Advanced competitor tracking", "included": True},
            {"name": "Website SEO workflows", "included": True},
            {"name": "Google Business Profile post scheduling", "included": True},
            {"name": "Call tracking setup support", "included": True},
            {"name": "Priority support", "included": True},
            {"name": "Multi-location reporting", "included": True},
        ],
        "cta": "Start With a Free Audit",
        "popular": False,
    },
    PlanType.STARTER: {
        "name": "Starter",
        "period": "month",
        "description": "Core local SEO automation for a single location.",
        "target": "Owner-operated local businesses ready to automate Google Maps basics.",
        "features": [
            {"name": "Google Maps post drafts and publishing workflow", "included": True},
            {"name": "Review collection and AI response drafts", "included": True},
            {"name": "Basic KPI dashboard", "included": True},
            {"name": "Weekly performance reports", "included": True},
            {"name": "Instagram publishing tools", "included": False},
            {"name": "Content scheduler", "included": False},
            {"name": "Q&A response drafts", "included": False},
            {"name": "Competitor analysis", "included": False},
            {"name": "Website SEO workflows", "included": False},
        ],
        "cta": "Choose Starter",
        "popular": False,
    },
    PlanType.PRO: {
        "name": "Pro",
        "period": "month",
        "description": "More automation for growing locations that publish and respond often.",
        "target": "Restaurants, med spas, clinics, and service businesses with active demand.",
        "badge": "Best Value",
        "features": [
            {"name": "All Starter features", "included": True},
            {"name": "Instagram publishing tools", "included": True},
            {"name": "Content scheduler", "included": True},
            {"name": "Q&A response drafts", "included": True},
            {"name": "Review trend and competitor analysis", "included": True},
            {"name": "Website SEO basics", "included": True},
            {"name": "Missed Call Text Back", "included": False, "addon": True},
            {"name": "Review Booster", "included": False, "addon": True},
            {"name": "Social Auto-Responder", "included": False, "addon": True},
        ],
        "cta": "Choose Pro",
        "popular": True,
    },
    PlanType.PREMIUM: {
        "name": "Premium",
        "period": "month",
        "description": "Full local growth automation across calls, reviews, SEO, and social response.",
        "target": "Multi-channel local teams that need faster response and review growth.",
        "features": [
            {"name": "All Pro features", "included": True},
            {"name": "Missed Call Text Back", "included": True},
            {"name": "Review Booster (SMS/Email)", "included": True},
            {"name": "Website SEO workflows", "included": True},
            {"name": "Social Auto-Responder", "included": True},
            {"name": "Video Generator", "included": False, "addon": True},
        ],
        "cta": "Choose Premium",
        "popular": False,
    },
    PlanType.AGENCY: {
        "name": "Agency",
        "period": "location/month",
        "description": "Agency and franchise operations for managing many local clients or locations.",
        "target": "Marketing agencies, franchise operators, and multi-location teams.",
        "features": [
            {"name": "All Premium features", "included": True},
            {"name": "White-label reports", "included": True},
            {"name": "Team permission management", "included": True},
            {"name": "Unified agency dashboard", "included": True},
            {"name": "Multi-location management", "included": True},
            {"name": "Bulk automation workflows", "included": True},
            {"name": "Video Generator", "included": True},
        ],
        "cta": "Contact Sales",
        "popular": False,
    },
}

_ADDON_COPY: dict[AddOnType, dict[str, str]] = {
    AddOnType.MISSED_CALL_TEXT_BACK: {
        "name": "Missed Call Text Back",
        "description": "Automatically text missed callers so owners can recover high-intent leads.",
    },
    AddOnType.REVIEW_BOOSTER: {
        "name": "Review Booster",
        "description": "Send review requests by SMS or email and track request outcomes.",
    },
    AddOnType.WEBSITE_SEO: {
        "name": "Website SEO Upgrade",
        "description": "Generate service-page and blog SEO workflows from live business context.",
    },
    AddOnType.SOCIAL_AUTO_RESPONDER: {
        "name": "Social Auto-Responder",
        "description": "Draft and send Instagram DM and comment responses from connected channels.",
    },
    AddOnType.VIDEO_GENERATOR: {
        "name": "Short Video Generator",
        "description": "Create short-form video assets for reels and local promotions.",
    },
}


def _pricing_plan(plan: PlanType) -> dict[str, Any]:
    plan_copy = _PLAN_COPY[plan]
    return {
        "id": plan.value,
        "name": plan_copy["name"],
        "price": PLAN_PRICES[plan],
        "period": plan_copy["period"],
        "description": plan_copy["description"],
        "target": plan_copy["target"],
        "features": plan_copy["features"],
        "cta": plan_copy["cta"],
        "popular": plan_copy["popular"],
        **({"setup_fee": plan_copy["setup_fee"]} if "setup_fee" in plan_copy else {}),
        **({"sales_motion": plan_copy["sales_motion"]} if "sales_motion" in plan_copy else {}),
        **({"badge": plan_copy["badge"]} if "badge" in plan_copy else {}),
    }


def _pricing_addon(addon: AddOnType) -> dict[str, Any]:
    addon_copy = _ADDON_COPY[addon]
    return {
        "id": addon.value,
        "name": addon_copy["name"],
        "price": ADDON_PRICES[addon],
        "description": addon_copy["description"],
    }


def get_pricing_data() -> dict[str, Any]:
    """Get complete pricing data for frontend display."""
    plans = [
        PlanType.MAPS_STARTER,
        PlanType.CALLS_GROWTH,
        PlanType.COMPETITIVE_MARKET,
    ]
    addons = [
        AddOnType.MISSED_CALL_TEXT_BACK,
        AddOnType.REVIEW_BOOSTER,
        AddOnType.WEBSITE_SEO,
        AddOnType.SOCIAL_AUTO_RESPONDER,
        AddOnType.VIDEO_GENERATOR,
    ]

    return {
        "plans": [_pricing_plan(plan) for plan in plans],
        "addons": [_pricing_addon(addon) for addon in addons],
        "trial": {
            "days": FREE_PREVIEW_DAYS,
            "features": [
                "Free dashboard preview",
                "Google Maps audit review",
                "Connection and setup health checks",
            ],
            "limitations": [
                "AI generation requires a paid plan",
                "SMS and missed-call text back require a paid plan or add-on",
                "Publishing to Google, Instagram, or Website requires a paid plan",
                "Missed Call Text Back is included from Calls Growth",
                "Review Booster is included from Calls Growth",
                "Website SEO full workflows require Competitive Market",
                "Multi-location operations require Competitive Market or a custom managed scope",
            ],
        },
        "comparison": {
            "agency_price": "$2,000+/month",
            "our_price": "$699-$1,499/month",
            "savings": "Managed pilot pricing is lower than a typical full-service agency retainer while preserving operator support",
        },
    }
