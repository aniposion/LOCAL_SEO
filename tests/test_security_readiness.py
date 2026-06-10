"""Tests for production-readiness guards and security headers."""

from app.core.config import settings
from app.core.production_readiness import validate_runtime_settings


def _set_valid_public_launch_config(monkeypatch) -> None:
    """Patch the shared settings object into a launch-ready production shape."""
    monkeypatch.setattr(settings, "app_env", "prod")
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg2://seo:pw@db:5432/app")
    monkeypatch.setattr(settings, "app_url", "https://app.example.com")
    monkeypatch.setattr(settings, "jwt_secret", "a" * 48)
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_live_123")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_live_123")
    monkeypatch.setattr(settings, "stripe_price_maps_starter_monthly", "price_live_maps_starter_monthly")
    monkeypatch.setattr(settings, "stripe_price_maps_starter_yearly", "price_live_maps_starter_yearly")
    monkeypatch.setattr(settings, "stripe_price_calls_growth_monthly", "price_live_calls_growth_monthly")
    monkeypatch.setattr(settings, "stripe_price_calls_growth_yearly", "price_live_calls_growth_yearly")
    monkeypatch.setattr(settings, "stripe_price_competitive_market_monthly", "price_live_competitive_market_monthly")
    monkeypatch.setattr(settings, "stripe_price_competitive_market_yearly", "price_live_competitive_market_yearly")
    monkeypatch.setattr(settings, "stripe_price_starter_monthly", "price_live_starter_monthly")
    monkeypatch.setattr(settings, "stripe_price_starter_yearly", "price_live_starter_yearly")
    monkeypatch.setattr(settings, "stripe_price_pro_monthly", "price_live_pro_monthly")
    monkeypatch.setattr(settings, "stripe_price_pro_yearly", "price_live_pro_yearly")
    monkeypatch.setattr(settings, "stripe_price_premium_monthly", "price_live_premium_monthly")
    monkeypatch.setattr(settings, "stripe_price_premium_yearly", "price_live_premium_yearly")
    monkeypatch.setattr(settings, "stripe_price_agency_monthly", "price_live_agency_monthly")
    monkeypatch.setattr(settings, "stripe_price_agency_yearly", "price_live_agency_yearly")
    monkeypatch.setattr(settings, "gcs_bucket", "prod-assets")
    monkeypatch.setattr(settings, "google_application_credentials", None)
    monkeypatch.setattr(settings, "s3_bucket", None)
    monkeypatch.setattr(settings, "aws_region", None)
    monkeypatch.setattr(settings, "aws_access_key_id", None)
    monkeypatch.setattr(settings, "aws_secret_access_key", None)
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "gemini-live")
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "gbp_client_id", "gbp-client")
    monkeypatch.setattr(settings, "gbp_client_secret", "gbp-secret")
    monkeypatch.setattr(settings, "ig_app_id", "ig-app")
    monkeypatch.setattr(settings, "ig_app_secret", "ig-secret")
    monkeypatch.setattr(settings, "sendgrid_api_key", "SG.live")
    monkeypatch.setattr(settings, "sendgrid_from_email", "billing@localseooptimizer.com")
    monkeypatch.setattr(settings, "scheduler_enabled", True)
    monkeypatch.setattr(settings, "scheduler_target", "all")
    monkeypatch.setattr(settings, "sentry_dsn", "https://sentry.example/1")
    monkeypatch.setattr(settings, "slack_webhook_url", "https://hooks.slack.com/services/live")


def test_health_response_includes_security_headers_and_request_id(client) -> None:
    """Health responses should include baseline security headers."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "X-Request-ID" in response.headers


def test_readyz_returns_ok_in_test_env(client) -> None:
    """Readiness should succeed in tests while still exposing warnings if present."""
    response = client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database_ok"] is True
    assert "config_errors" in data


def test_validate_runtime_settings_flags_prod_critical_issues(monkeypatch) -> None:
    """Production validation should catch obviously unsafe config."""
    monkeypatch.setattr(settings, "app_env", "prod")
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "database_url", "sqlite:///./bad.db")
    monkeypatch.setattr(settings, "app_url", "http://localhost:3000")
    monkeypatch.setattr(settings, "jwt_secret", "replace-with-a-strong-random-secret-at-least-32-characters")
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_live_example")
    monkeypatch.setattr(settings, "stripe_webhook_secret", None)

    readiness = validate_runtime_settings(settings)

    assert any("DEBUG must be false" in item for item in readiness["errors"])
    assert any("cannot run on SQLite" in item for item in readiness["errors"])
    assert any("must use https" in item for item in readiness["errors"])
    assert any("public production host" in item for item in readiness["errors"])
    assert any("JWT_SECRET" in item for item in readiness["errors"])
    assert any("STRIPE_WEBHOOK_SECRET" in item for item in readiness["errors"])


def test_validate_runtime_settings_blocks_missing_prod_launch_dependencies(monkeypatch) -> None:
    """Public production launch should fail fast when core integrations are absent."""
    monkeypatch.setattr(settings, "app_env", "prod")
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg2://seo:pw@db:5432/app")
    monkeypatch.setattr(settings, "app_url", "https://app.example.com")
    monkeypatch.setattr(settings, "jwt_secret", "a" * 48)
    monkeypatch.setattr(settings, "stripe_secret_key", None)
    monkeypatch.setattr(settings, "stripe_webhook_secret", None)
    monkeypatch.setattr(settings, "stripe_price_maps_starter_monthly", "price_maps_starter_monthly")
    monkeypatch.setattr(settings, "stripe_price_maps_starter_yearly", None)
    monkeypatch.setattr(settings, "stripe_price_calls_growth_monthly", None)
    monkeypatch.setattr(settings, "stripe_price_calls_growth_yearly", None)
    monkeypatch.setattr(settings, "stripe_price_competitive_market_monthly", None)
    monkeypatch.setattr(settings, "stripe_price_competitive_market_yearly", None)
    monkeypatch.setattr(settings, "stripe_price_starter_monthly", "price_starter_monthly")
    monkeypatch.setattr(settings, "stripe_price_starter_yearly", None)
    monkeypatch.setattr(settings, "stripe_price_pro_monthly", None)
    monkeypatch.setattr(settings, "stripe_price_pro_yearly", None)
    monkeypatch.setattr(settings, "stripe_price_premium_monthly", None)
    monkeypatch.setattr(settings, "stripe_price_premium_yearly", None)
    monkeypatch.setattr(settings, "stripe_price_agency_monthly", None)
    monkeypatch.setattr(settings, "stripe_price_agency_yearly", None)
    monkeypatch.setattr(settings, "gcs_bucket", None)
    monkeypatch.setattr(settings, "s3_bucket", None)
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "gemini_api_key", None)
    monkeypatch.setattr(settings, "gbp_client_id", None)
    monkeypatch.setattr(settings, "gbp_client_secret", None)
    monkeypatch.setattr(settings, "ig_app_id", None)
    monkeypatch.setattr(settings, "ig_app_secret", None)
    monkeypatch.setattr(settings, "sendgrid_api_key", None)
    monkeypatch.setattr(settings, "sendgrid_from_email", None)
    monkeypatch.setattr(settings, "scheduler_enabled", False)

    readiness = validate_runtime_settings(settings)

    assert any("STRIPE_SECRET_KEY" in item for item in readiness["errors"])
    assert any("STRIPE_WEBHOOK_SECRET" in item for item in readiness["errors"])
    assert any("Stripe managed pilot price IDs" in item for item in readiness["errors"])
    assert any("Cloud storage" in item for item in readiness["errors"])
    assert any("No LLM API key" in item for item in readiness["errors"])
    assert any("Google Business Profile OAuth" in item for item in readiness["errors"])
    assert any("Instagram publishing OAuth" in item for item in readiness["errors"])
    assert any("SENDGRID_API_KEY" in item for item in readiness["errors"])
    assert any("Schedulers are disabled" in item for item in readiness["warnings"])


def test_validate_runtime_settings_allows_prod_gcs_with_ambient_auth(monkeypatch) -> None:
    """Cloud Run production can rely on ambient service-account auth for GCS."""
    _set_valid_public_launch_config(monkeypatch)

    readiness = validate_runtime_settings(settings)

    assert readiness["errors"] == []
    assert not any("GOOGLE_APPLICATION_CREDENTIALS" in item for item in readiness["warnings"])


def test_validate_runtime_settings_warns_for_gcs_without_local_credentials_outside_prod(monkeypatch) -> None:
    """Local and staging-style environments should still surface missing file credentials."""
    monkeypatch.setattr(settings, "app_env", "dev")
    monkeypatch.setattr(settings, "gcs_bucket", "dev-assets")
    monkeypatch.setattr(settings, "google_application_credentials", None)
    monkeypatch.setattr(settings, "s3_bucket", None)

    readiness = validate_runtime_settings(settings)

    assert any("GOOGLE_APPLICATION_CREDENTIALS" in item for item in readiness["warnings"])
