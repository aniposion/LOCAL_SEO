"""Schemas module exports."""

from app.schemas.account import AccountCreate, AccountResponse, AccountUpdate
from app.schemas.analytics import (
    AnalyticsCreate,
    AnalyticsResponse,
    AnalyticsSummary,
    GBPIngestRequest,
    IGIngestRequest,
)
from app.schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    RefreshRequest,
    SignupRequest,
    TokenResponse,
)
from app.schemas.billing import (
    SubscribeRequest,
    SubscribeResponse,
    SubscriptionStatus,
    WebhookEvent,
)
from app.schemas.channel import (
    ChannelCreate,
    ChannelCredentials,
    ChannelResponse,
    ChannelUpdate,
)
from app.schemas.content import (
    ContentGenerateRequest,
    ContentGenerateResponse,
    GeneratedContent,
    GBPContent,
    InstagramContent,
    WebContent,
)
from app.schemas.location import (
    LocationCreate,
    LocationHealth,
    LocationResponse,
    LocationUpdate,
)
from app.schemas.post import (
    PostBulkCreate,
    PostCreate,
    PostPublishRequest,
    PostResponse,
    PostUpdate,
)
from app.schemas.report import (
    ReportCreate,
    ReportGenerateRequest,
    ReportResponse,
    ReportSummary,
)
from app.schemas.schedule import ScheduleCreate, ScheduleResponse, ScheduleUpdate
from app.schemas.seo import (
    SEORecalcRequest,
    SEORecommendation,
    SEOScoreCreate,
    SEOScoreResponse,
    SEOTrend,
)

__all__ = [
    # Auth
    "SignupRequest",
    "LoginRequest",
    "TokenResponse",
    "RefreshRequest",
    "PasswordChangeRequest",
    # Account
    "AccountCreate",
    "AccountUpdate",
    "AccountResponse",
    # Location
    "LocationCreate",
    "LocationUpdate",
    "LocationResponse",
    "LocationHealth",
    # Channel
    "ChannelCreate",
    "ChannelUpdate",
    "ChannelResponse",
    "ChannelCredentials",
    # Post
    "PostCreate",
    "PostUpdate",
    "PostResponse",
    "PostPublishRequest",
    "PostBulkCreate",
    # Content
    "ContentGenerateRequest",
    "ContentGenerateResponse",
    "GeneratedContent",
    "GBPContent",
    "InstagramContent",
    "WebContent",
    # Analytics
    "AnalyticsCreate",
    "AnalyticsResponse",
    "AnalyticsSummary",
    "GBPIngestRequest",
    "IGIngestRequest",
    # SEO
    "SEOScoreCreate",
    "SEOScoreResponse",
    "SEORecalcRequest",
    "SEORecommendation",
    "SEOTrend",
    # Report
    "ReportCreate",
    "ReportResponse",
    "ReportGenerateRequest",
    "ReportSummary",
    # Schedule
    "ScheduleCreate",
    "ScheduleUpdate",
    "ScheduleResponse",
    # Billing
    "SubscribeRequest",
    "SubscribeResponse",
    "SubscriptionStatus",
    "WebhookEvent",
]
