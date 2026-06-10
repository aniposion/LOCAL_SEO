"""Optional error tracking bootstrap."""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def init_error_tracking() -> None:
    """Initialize Sentry when configured and available.

    The app stays functional if the SDK is not installed or no DSN is configured.
    """
    if not settings.sentry_dsn:
        return

    try:
        import sentry_sdk
    except ModuleNotFoundError:
        logger.warning(
            "SENTRY_DSN is configured but sentry-sdk is not installed. Error tracking is disabled."
        )
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        release=settings.app_version,
        traces_sample_rate=0.0,
        send_default_pii=False,
    )
    logger.info("Sentry error tracking initialized for environment=%s", settings.app_env)
