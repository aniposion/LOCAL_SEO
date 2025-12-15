"""Routers module exports."""

from app.routers.ab_testing import router as ab_testing_router
from app.routers.admin import router as admin_router
from app.routers.agency import router as agency_router
from app.routers.analytics import router as analytics_router
from app.routers.approval import router as approval_router
from app.routers.auth import router as auth_router
from app.routers.billing import router as billing_router
from app.routers.calls import router as calls_router
from app.routers.content import router as content_router
from app.routers.locations import router as locations_router
from app.routers.magic_approval import router as magic_approval_router
from app.routers.notifications import router as notifications_router
from app.routers.oauth import router as oauth_router
from app.routers.onboarding import router as onboarding_router
from app.routers.posts import router as posts_router
from app.routers.qa import router as qa_router
from app.routers.reports import router as reports_router
from app.routers.review_booster import router as review_booster_router
from app.routers.seo import router as seo_router
from app.routers.social import router as social_router
from app.routers.uploads import router as uploads_router
from app.routers.usage import router as usage_router
from app.routers.webhooks import router as webhooks_router
from app.routers.website_seo import router as website_seo_router

__all__ = [
    "ab_testing_router",
    "admin_router",
    "agency_router",
    "analytics_router",
    "approval_router",
    "auth_router",
    "billing_router",
    "calls_router",
    "content_router",
    "locations_router",
    "magic_approval_router",
    "notifications_router",
    "oauth_router",
    "onboarding_router",
    "posts_router",
    "qa_router",
    "reports_router",
    "review_booster_router",
    "seo_router",
    "social_router",
    "uploads_router",
    "usage_router",
    "webhooks_router",
    "website_seo_router",
]
