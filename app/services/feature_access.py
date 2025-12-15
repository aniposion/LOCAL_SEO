"""Feature access control service."""

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.subscription import (
    Subscription,
    PlanType,
    AddOnType,
    PLAN_FEATURES,
    PLAN_PRICES,
    ADDON_PRICES,
    SubscriptionStatus,
)


class FeatureAccessService:
    """Service for checking feature access based on subscription."""

    def __init__(self, db: Session):
        self.db = db

    def get_subscription(self, account_id: UUID) -> Subscription | None:
        """Get subscription for an account."""
        return self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

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
        subscription = self.get_subscription(account.id)
        
        if not subscription:
            # No subscription = free plan
            has_access = PLAN_FEATURES[PlanType.FREE].get(feature, False)
        elif not subscription.is_active:
            # Inactive subscription = no access
            has_access = False
        else:
            has_access = subscription.has_feature(feature)
        
        if not has_access and raise_exception:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "feature_not_available",
                    "feature": feature,
                    "message": f"This feature requires a higher plan or add-on.",
                    "upgrade_url": "/pricing",
                }
            )
        
        return has_access

    def get_account_features(self, account: Account) -> dict[str, Any]:
        """Get all features available to an account."""
        subscription = self.get_subscription(account.id)
        
        if not subscription:
            return {
                "plan": "free",
                "status": "none",
                "is_trial": False,
                "features": PLAN_FEATURES[PlanType.FREE],
                "active_addons": [],
                "monthly_price": 0,
            }
        
        return {
            "plan": subscription.plan_type.value,
            "status": subscription.status.value,
            "is_trial": subscription.is_trial,
            "trial_end": subscription.trial_end.isoformat() if subscription.trial_end else None,
            "features": subscription.get_features(),
            "active_addons": subscription.active_addons or [],
            "monthly_price": subscription.get_monthly_price(),
            "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
        }

    def get_upgrade_options(self, account: Account) -> dict[str, Any]:
        """Get available upgrade options for an account."""
        subscription = self.get_subscription(account.id)
        current_plan = subscription.plan_type if subscription else PlanType.FREE
        
        # Plans that are upgrades from current
        plan_order = [PlanType.FREE, PlanType.STARTER, PlanType.PRO, PlanType.PREMIUM, PlanType.AGENCY]
        current_index = plan_order.index(current_plan)
        
        available_plans = []
        for plan in plan_order[current_index + 1:]:
            available_plans.append({
                "plan": plan.value,
                "price": PLAN_PRICES[plan],
                "features": PLAN_FEATURES[plan],
            })
        
        # Available add-ons (not already active)
        active_addons = subscription.active_addons if subscription else []
        available_addons = []
        
        for addon in AddOnType:
            if addon.value not in active_addons:
                # Check if this addon makes sense for current plan
                # (e.g., don't show addons that are already included in plan)
                feature_name = {
                    AddOnType.MISSED_CALL_TEXT_BACK: "missed_call_text_back",
                    AddOnType.REVIEW_BOOSTER: "review_booster",
                    AddOnType.WEBSITE_SEO: "website_seo_full",
                    AddOnType.SOCIAL_AUTO_RESPONDER: "social_auto_responder",
                    AddOnType.VIDEO_GENERATOR: "video_generator",
                }.get(addon)
                
                plan_features = PLAN_FEATURES.get(current_plan, {})
                if not plan_features.get(feature_name, False):
                    available_addons.append({
                        "addon": addon.value,
                        "name": addon.value.replace("_", " ").title(),
                        "price": ADDON_PRICES[addon],
                    })
        
        return {
            "current_plan": current_plan.value,
            "available_plans": available_plans,
            "available_addons": available_addons,
        }


# Feature check decorator for routes
def require_feature(feature: str):
    """Decorator to require a specific feature for a route."""
    from functools import wraps
    from fastapi import Depends
    from app.routers.deps import get_db, get_current_user
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get db and current_user from kwargs (injected by FastAPI)
            db = kwargs.get('db')
            current_user = kwargs.get('current_user')
            
            if db and current_user:
                service = FeatureAccessService(db)
                service.check_feature_access(current_user, feature)
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Pricing data for frontend
def get_pricing_data() -> dict[str, Any]:
    """Get complete pricing data for frontend display."""
    return {
        "plans": [
            {
                "id": "starter",
                "name": "Starter",
                "price": 99,
                "period": "month",
                "description": "핵심 기능만 경험시키고, 업셀을 유도하는 플랜",
                "target": "동네 식당, 스몰 비즈니스, 1인 운영업체",
                "features": [
                    {"name": "Google Maps 포스트 자동 생성 & 업로드", "included": True},
                    {"name": "리뷰 자동 수집 + AI 답변 초안", "included": True},
                    {"name": "기본 KPI 대시보드", "included": True},
                    {"name": "주간 리포트", "included": True},
                    {"name": "Instagram 업로드", "included": False},
                    {"name": "콘텐츠 예약 (Scheduler)", "included": False},
                    {"name": "Q&A 자동 응답", "included": False},
                    {"name": "경쟁사 분석", "included": False},
                    {"name": "Website SEO", "included": False},
                ],
                "cta": "Start Free Trial",
                "popular": False,
            },
            {
                "id": "pro",
                "name": "Pro",
                "price": 149,
                "period": "month",
                "description": "진짜 돈을 벌어주는 기능들이 이 플랜에서 시작된다",
                "target": "스파, 식당, 클리닉, 오토샵 등",
                "badge": "Best Value",
                "features": [
                    {"name": "Starter 기능 전부", "included": True},
                    {"name": "Instagram 자동 업로드", "included": True},
                    {"name": "콘텐츠 예약 (Scheduler)", "included": True},
                    {"name": "Q&A 자동 응답 초안", "included": True},
                    {"name": "리뷰 트렌드 분석 (경쟁사 포함)", "included": True},
                    {"name": "Website SEO 기본", "included": True},
                    {"name": "Missed Call Text Back", "included": False, "addon": True},
                    {"name": "Review Booster", "included": False, "addon": True},
                    {"name": "Social Auto-Responder", "included": False, "addon": True},
                ],
                "cta": "Start Free Trial",
                "popular": True,
            },
            {
                "id": "premium",
                "name": "Premium",
                "price": 249,
                "period": "month",
                "description": "전화·리뷰·예약까지 매출 전환을 극대화하는 플랜",
                "target": "인기 식당, Med Spa, 뷰티샵, 고단가 업종",
                "features": [
                    {"name": "Pro 기능 전부", "included": True},
                    {"name": "Missed Call Text Back", "included": True},
                    {"name": "Review Booster (SMS/Email)", "included": True},
                    {"name": "Website SEO Full", "included": True},
                    {"name": "Social Auto-Responder", "included": True},
                    {"name": "Video Generator", "included": False, "addon": True},
                ],
                "cta": "Start Free Trial",
                "popular": False,
            },
            {
                "id": "agency",
                "name": "Agency",
                "price": 499,
                "period": "location/month",
                "description": "프랜차이즈 및 에이전시를 위한 플랜",
                "target": "마케팅 에이전시, 프랜차이즈",
                "features": [
                    {"name": "Premium 기능 전부", "included": True},
                    {"name": "White Label 보고서", "included": True},
                    {"name": "팀 계정 권한 관리", "included": True},
                    {"name": "대시보드 통합", "included": True},
                    {"name": "다중 매장 운영", "included": True},
                    {"name": "작업 자동 배포", "included": True},
                    {"name": "Video Generator", "included": True},
                ],
                "cta": "Contact Sales",
                "popular": False,
            },
        ],
        "addons": [
            {
                "id": "missed_call_text_back",
                "name": "Missed Call Text Back",
                "price": 29,
                "description": "부재중 전화 문자 자동응답",
            },
            {
                "id": "review_booster",
                "name": "Review Booster",
                "price": 39,
                "description": "리뷰 요청 SMS/Email 자동 발송",
            },
            {
                "id": "website_seo",
                "name": "Website SEO Upgrade",
                "price": 49,
                "description": "키워드 연구 + 블로그 자동 생성",
            },
            {
                "id": "social_auto_responder",
                "name": "Social Auto-Responder",
                "price": 29,
                "description": "IG DM/댓글 자동응답",
            },
            {
                "id": "video_generator",
                "name": "Short Video Generator",
                "price": 49,
                "description": "릴스/쇼츠 자동 생성",
            },
        ],
        "trial": {
            "days": 7,
            "features": [
                "Google Posts 2개 생성",
                "Instagram 2개 업로드",
                "리뷰 1~2개 AI 응답",
            ],
            "limitations": [
                "Missed Call Text Back - 기능 알림만",
                "Review Booster - 샘플 메시지만",
                "Website SEO - 분석까지만",
                "Agency 기능 없음",
            ],
        },
        "comparison": {
            "agency_price": "$2,000+/월",
            "our_price": "$99-249/월",
            "savings": "최대 90% 절감",
        },
    }
