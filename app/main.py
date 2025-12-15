"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import (
    ab_testing_router,
    admin_router,
    agency_router,
    analytics_router,
    approval_router,
    auth_router,
    billing_router,
    calls_router,
    content_router,
    locations_router,
    magic_approval_router,
    notifications_router,
    oauth_router,
    onboarding_router,
    posts_router,
    qa_router,
    reports_router,
    review_booster_router,
    seo_router,
    social_router,
    uploads_router,
    usage_router,
    webhooks_router,
    website_seo_router,
)
from app.workers.scheduler import setup_scheduler, shutdown_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    if settings.app_env != "test":
        setup_scheduler()
    yield
    # Shutdown
    if settings.app_env != "test":
        shutdown_scheduler()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Local SEO Optimizer - Automated content generation and SEO management for local businesses",
    lifespan=lifespan,
    docs_url="/docs" if settings.app_env != "prod" else None,
    redoc_url="/redoc" if settings.app_env != "prod" else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env == "dev" else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(oauth_router)
app.include_router(onboarding_router)
app.include_router(approval_router)
app.include_router(magic_approval_router)
app.include_router(locations_router)
app.include_router(content_router)
app.include_router(posts_router)
app.include_router(analytics_router)
app.include_router(seo_router)
app.include_router(reports_router)
app.include_router(billing_router)
app.include_router(webhooks_router)
app.include_router(review_booster_router)
app.include_router(website_seo_router)
app.include_router(agency_router)
app.include_router(qa_router)
app.include_router(calls_router)
app.include_router(social_router)
app.include_router(notifications_router)
app.include_router(ab_testing_router)
app.include_router(uploads_router)
app.include_router(usage_router)
app.include_router(admin_router)


@app.get("/healthz", tags=["health"])
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}


@app.get("/", tags=["root"])
async def root() -> dict:
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }
