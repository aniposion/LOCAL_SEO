"""FastAPI application entry point."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import settings
from app.core.http import (
    RequestContextMiddleware,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.production_readiness import allowed_hosts_from_app_url, validate_runtime_settings
from app.core.telemetry import init_error_tracking
from app.db.session import engine
from app.jobs.scheduler import (
    shutdown_scheduler as shutdown_jobs_scheduler,
    start_scheduler as start_jobs_scheduler,
)
from app.scheduler_runtime import (
    shutdown_configured_schedulers as runtime_shutdown_configured_schedulers,
    start_configured_schedulers as runtime_start_configured_schedulers,
)
from app.routers import (
    ab_testing_router,
    admin_router,
    agency_router,
    analytics_router,
    approval_router,
    auth_router,
    billing_router,
    board_router,
    calls_router,
    contact_router,
    content_router,
    locations_router,
    magic_approval_router,
    notifications_router,
    oauth_router,
    onboarding_router,
    onboarding_progress_router,
    posts_router,
    qa_router,
    revenue_router,
    reports_router,
    review_booster_router,
    seo_router,
    social_router,
    uploads_router,
    usage_router,
    webhooks_router,
    website_seo_router,
    # P1: Metrics & Attribution
    metrics_router,
    proof_reports_router,
    utm_router,
    # P5: Entity Vault
    entity_vault_router,
    # P6: AI Content
    ai_content_router,
    # P7-P9: New AI Features
    competitor_router,
    review_responder_router,
    social_proof_router,
)
from app.workers.scheduler import (
    setup_scheduler as start_workers_scheduler,
    shutdown_scheduler as shutdown_workers_scheduler,
)

logger = logging.getLogger(__name__)


def _start_configured_schedulers() -> list[str]:
    """Start only the schedulers explicitly enabled for the API process."""
    return runtime_start_configured_schedulers(
        settings=settings,
        process_name="api",
        start_jobs_scheduler=start_jobs_scheduler,
        start_workers_scheduler=start_workers_scheduler,
    )


def _shutdown_configured_schedulers(started: list[str]) -> None:
    """Shutdown only the schedulers started by the API process."""
    runtime_shutdown_configured_schedulers(
        started=started,
        process_name="api",
        shutdown_jobs_scheduler=shutdown_jobs_scheduler,
        shutdown_workers_scheduler=shutdown_workers_scheduler,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    readiness = validate_runtime_settings(settings)
    for warning in readiness["warnings"]:
        logger.warning("Startup readiness warning: %s", warning)

    if settings.app_env == "prod" and readiness["errors"]:
        raise RuntimeError(
            "Production readiness validation failed: " + "; ".join(readiness["errors"])
        )

    init_error_tracking()

    # Startup
    started_schedulers = _start_configured_schedulers()
    yield
    # Shutdown
    _shutdown_configured_schedulers(started_schedulers)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Local SEO Optimizer - Automated content generation and SEO management for local businesses",
    lifespan=lifespan,
    docs_url="/docs" if settings.app_env != "prod" else None,
    redoc_url="/redoc" if settings.app_env != "prod" else None,
)

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

if settings.app_env in {"staging", "prod"}:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=allowed_hosts_from_app_url(settings.app_url),
    )

app.add_middleware(RequestContextMiddleware)

# CORS middleware
CORS_ORIGINS = {
    "dev": list({
        settings.app_url,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    }),
    "staging": [settings.app_url],
    "prod": [settings.app_url],
}
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS.get(settings.app_env, ["*"]),
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$" if settings.app_env == "dev" else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers.
# Root routes are canonical for direct app deployments. The /api/v1 aliases keep
# public callback URLs stable when a frontend or gateway is already configured
# with the conventional API prefix.
APP_ROUTERS = (
    auth_router,
    oauth_router,
    onboarding_router,
    onboarding_progress_router,
    approval_router,
    magic_approval_router,
    locations_router,
    content_router,
    posts_router,
    analytics_router,
    seo_router,
    # Register the more specific /reports/weekly routes before /reports/{report_id}.
    proof_reports_router,
    reports_router,
    billing_router,
    board_router,
    contact_router,
    webhooks_router,
    review_booster_router,
    website_seo_router,
    agency_router,
    qa_router,
    revenue_router,
    calls_router,
    social_router,
    notifications_router,
    ab_testing_router,
    uploads_router,
    usage_router,
    admin_router,
    # P1: Metrics & Attribution
    metrics_router,
    utm_router,
    # P5: Entity Vault
    entity_vault_router,
    # P6: AI Content
    ai_content_router,
    # P7-P9: New AI Features
    competitor_router,
    review_responder_router,
    social_proof_router,
)

for router in APP_ROUTERS:
    app.include_router(router)

for router in APP_ROUTERS:
    app.include_router(router, prefix="/api/v1")


@app.get("/healthz", tags=["health"])
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}


@app.get("/readyz", tags=["health"])
async def readiness_check() -> tuple[dict, int] | dict:
    """Readiness endpoint for deployment health gates."""
    readiness = validate_runtime_settings(settings)
    db_ok = True
    db_error = None

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - exercised by runtime, not unit tests
        db_ok = False
        db_error = str(exc)

    payload = {
        "status": "ready" if db_ok and not readiness["errors"] else "not_ready",
        "version": settings.app_version,
        "database_ok": db_ok,
        "config_errors": readiness["errors"],
        "warnings": readiness["warnings"],
    }
    if db_error:
        payload["database_error"] = db_error

    if db_ok and not readiness["errors"]:
        return payload
    return JSONResponse(status_code=503, content=payload)


@app.get("/api/v1/healthz", tags=["health"])
async def prefixed_health_check() -> dict:
    """Compatibility health check endpoint for /api/v1 deployments."""
    return await health_check()


@app.get("/api/v1/readyz", tags=["health"])
async def prefixed_readiness_check() -> tuple[dict, int] | dict:
    """Compatibility readiness endpoint for /api/v1 deployments."""
    return await readiness_check()


@app.get("/", tags=["root"])
async def root() -> dict:
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs" if settings.app_env != "prod" else None,
    }
