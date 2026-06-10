"""Production readiness validation helpers."""

from __future__ import annotations

from urllib.parse import urlparse

from app.core.config import Settings


def _is_placeholder(value: str | None) -> bool:
    """Treat common template values as effectively unset."""
    if not value:
        return True
    lowered = value.strip().lower()
    placeholders = (
        "changeme",
        "replace_with",
        "replace-with",
        "your_",
        "your-",
        "example",
        "localhost",
        "sk_test_...",
        "whsec_...",
        "dummy",
        "todo",
    )
    return any(token in lowered for token in placeholders)


def _configured(value: str | None) -> bool:
    """Return whether a config value is present and not an obvious template."""
    return not _is_placeholder(value)


def _all_configured(*values: str | None) -> bool:
    return all(_configured(value) for value in values)


def _warn_or_error(
    *,
    is_prod: bool,
    errors: list[str],
    warnings: list[str],
    message: str,
) -> None:
    """Promote public-launch blockers to prod errors while keeping dev useful."""
    if is_prod:
        errors.append(message)
    else:
        warnings.append(message)


def _is_example_price_id(value: str | None) -> bool:
    """Catch .env example Stripe price IDs that look configured but are not real."""
    if _is_placeholder(value):
        return True

    lowered = value.strip().lower()
    example_price_ids = {
        "price_maps_starter_monthly",
        "price_maps_starter_yearly",
        "price_calls_growth_monthly",
        "price_calls_growth_yearly",
        "price_competitive_market_monthly",
        "price_competitive_market_yearly",
        "price_starter_monthly",
        "price_starter_yearly",
        "price_pro_monthly",
        "price_pro_yearly",
        "price_premium_monthly",
        "price_premium_yearly",
        "price_agency_monthly",
        "price_agency_yearly",
    }
    return lowered in example_price_ids


def validate_runtime_settings(settings: Settings) -> dict[str, list[str]]:
    """Return critical errors and warnings for the current runtime settings."""
    errors: list[str] = []
    warnings: list[str] = []

    parsed_app_url = urlparse(settings.app_url)
    app_host = parsed_app_url.hostname or ""
    is_prod = settings.app_env == "prod"

    if is_prod and settings.debug:
        errors.append("DEBUG must be false in production.")

    if is_prod and str(settings.database_url).startswith("sqlite"):
        errors.append("Production cannot run on SQLite. Use PostgreSQL.")

    if is_prod and (not parsed_app_url.scheme or parsed_app_url.scheme != "https"):
        errors.append("APP_URL must use https in production.")

    if is_prod and app_host in {"", "localhost", "127.0.0.1"}:
        errors.append("APP_URL must point to the public production host.")

    if _is_placeholder(settings.jwt_secret):
        if is_prod:
            errors.append("JWT_SECRET must be replaced with a strong production value.")
        else:
            warnings.append("JWT_SECRET still looks like a placeholder value.")

    if _is_placeholder(settings.stripe_secret_key):
        _warn_or_error(
            is_prod=is_prod,
            errors=errors,
            warnings=warnings,
            message="STRIPE_SECRET_KEY must be configured for billing.",
        )
    elif is_prod and not settings.stripe_secret_key.startswith("sk_live_"):
        errors.append("STRIPE_SECRET_KEY must be a live Stripe secret key in production.")

    if _is_placeholder(settings.stripe_webhook_secret):
        _warn_or_error(
            is_prod=is_prod,
            errors=errors,
            warnings=warnings,
            message="STRIPE_WEBHOOK_SECRET must be configured for billing webhooks.",
        )

    if settings.stripe_secret_key and not settings.stripe_webhook_secret:
        errors.append("STRIPE_WEBHOOK_SECRET is required when Stripe billing is enabled.")

    if settings.stripe_webhook_secret and not settings.stripe_secret_key:
        errors.append("STRIPE_SECRET_KEY is required when Stripe webhooks are enabled.")

    plan_price_ids = {
        "STRIPE_PRICE_MAPS_STARTER_MONTHLY": settings.stripe_price_maps_starter_monthly,
        "STRIPE_PRICE_MAPS_STARTER_YEARLY": settings.stripe_price_maps_starter_yearly,
        "STRIPE_PRICE_CALLS_GROWTH_MONTHLY": settings.stripe_price_calls_growth_monthly,
        "STRIPE_PRICE_CALLS_GROWTH_YEARLY": settings.stripe_price_calls_growth_yearly,
        "STRIPE_PRICE_COMPETITIVE_MARKET_MONTHLY": settings.stripe_price_competitive_market_monthly,
        "STRIPE_PRICE_COMPETITIVE_MARKET_YEARLY": settings.stripe_price_competitive_market_yearly,
    }
    missing_price_ids = [
        name for name, value in plan_price_ids.items() if _is_example_price_id(value)
    ]
    if missing_price_ids:
        _warn_or_error(
            is_prod=is_prod,
            errors=errors,
            warnings=warnings,
            message=(
                "Stripe managed pilot price IDs must be configured for public checkout: "
                + ", ".join(missing_price_ids)
            ),
        )

    if settings.twilio_account_sid and (
        not settings.twilio_auth_token or not settings.twilio_phone_number
    ):
        errors.append(
            "TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER are required when Twilio is enabled."
        )

    if settings.sendgrid_api_key and not settings.sendgrid_from_email:
        errors.append("SENDGRID_FROM_EMAIL is required when SendGrid is enabled.")

    if is_prod and not _all_configured(settings.sendgrid_api_key, settings.sendgrid_from_email):
        errors.append(
            "SENDGRID_API_KEY and SENDGRID_FROM_EMAIL are required for production billing and lifecycle emails."
        )

    if settings.gcs_bucket and not settings.google_application_credentials and not is_prod:
        warnings.append(
            "GCS_BUCKET is set but GOOGLE_APPLICATION_CREDENTIALS is missing for local or non-Cloud Run environments."
        )

    if settings.s3_bucket and not _all_configured(
        settings.aws_region,
        settings.aws_access_key_id,
        settings.aws_secret_access_key,
    ):
        errors.append(
            "AWS_REGION, AWS_ACCESS_KEY_ID, and AWS_SECRET_ACCESS_KEY are required when S3_BUCKET is set."
        )

    storage_configured = _configured(settings.gcs_bucket) or _all_configured(
        settings.s3_bucket,
        settings.aws_region,
        settings.aws_access_key_id,
        settings.aws_secret_access_key,
    )
    if not storage_configured:
        _warn_or_error(
            is_prod=is_prod,
            errors=errors,
            warnings=warnings,
            message="Cloud storage is not configured. Upload-backed features will fail.",
        )

    if not settings.openai_api_key and not settings.gemini_api_key:
        _warn_or_error(
            is_prod=is_prod,
            errors=errors,
            warnings=warnings,
            message="No LLM API key is configured. AI generation features will be unavailable.",
        )
    elif (
        is_prod
        and settings.llm_provider == "openai"
        and not _configured(settings.openai_api_key)
    ):
        errors.append("OPENAI_API_KEY is required when LLM_PROVIDER=openai in production.")
    elif (
        is_prod
        and settings.llm_provider == "gemini"
        and not _configured(settings.gemini_api_key)
    ):
        errors.append("GEMINI_API_KEY is required when LLM_PROVIDER=gemini in production.")

    if not settings.gbp_client_id or not settings.gbp_client_secret:
        _warn_or_error(
            is_prod=is_prod,
            errors=errors,
            warnings=warnings,
            message="Google Business Profile OAuth is not fully configured.",
        )

    if not settings.ig_app_id or not settings.ig_app_secret:
        _warn_or_error(
            is_prod=is_prod,
            errors=errors,
            warnings=warnings,
            message="Instagram publishing OAuth is not fully configured.",
        )

    if is_prod and not settings.scheduler_enabled:
        warnings.append(
            "Schedulers are disabled in this process. Ensure a dedicated worker runs with "
            "SCHEDULER_ENABLED=true and SCHEDULER_TARGET=workers or all."
        )

    if is_prod and settings.scheduler_enabled and settings.scheduler_target == "jobs":
        warnings.append(
            "SCHEDULER_TARGET=jobs does not run publisher, analytics, weekly report, or billing worker jobs."
        )

    if is_prod and not settings.sentry_dsn:
        warnings.append("SENTRY_DSN is not configured. Runtime exception tracking will be limited.")

    if is_prod and not settings.slack_webhook_url:
        warnings.append(
            "SLACK_WEBHOOK_URL is not configured. Admin inbox will be the primary ops alert channel."
        )

    return {"errors": errors, "warnings": warnings}


def allowed_hosts_from_app_url(app_url: str) -> list[str]:
    """Build a conservative host allow-list for TrustedHost middleware."""
    parsed = urlparse(app_url)
    host = parsed.hostname
    hosts = {"localhost", "127.0.0.1"}
    if host:
        hosts.add(host)
        if host.startswith("www."):
            hosts.add(host.removeprefix("www."))
        else:
            hosts.add(f"www.{host}")
    return sorted(hosts)
