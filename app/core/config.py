"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: Literal["dev", "staging", "prod"] = "dev"
    app_name: str = "Local SEO Optimizer"
    app_version: str = "0.1.0"
    debug: bool = False
    scheduler_enabled: bool = False
    scheduler_target: Literal["jobs", "workers", "all"] = "jobs"

    # Database
    database_url: str = Field(
        default="sqlite:///./local_seo.db"
    )

    # JWT
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    auth_cookie_path: str = "/"
    oauth_state_ttl_seconds: int = 900

    # Google Cloud Storage
    gcs_bucket: str | None = None
    gcs_project_id: str | None = None
    google_application_credentials: str | None = None

    # AWS S3 (optional alternative to GCS for public file links)
    s3_bucket: str | None = None
    aws_region: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    # Stripe
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None

    # Google Business Profile (P4: OAuth)
    gbp_api_key: str | None = None
    gbp_client_id: str | None = None
    gbp_client_secret: str | None = None
    
    # Alias for google_api_service
    @property
    def google_client_id(self) -> str | None:
        return self.gbp_client_id
    
    @property
    def google_client_secret(self) -> str | None:
        return self.gbp_client_secret

    # Facebook (P4: OAuth)
    facebook_app_id: str | None = None
    facebook_app_secret: str | None = None

    # Instagram
    ig_app_id: str | None = None
    ig_app_secret: str | None = None
    
    # Alias for Instagram
    @property
    def instagram_client_id(self) -> str | None:
        return self.ig_app_id
    
    @property
    def instagram_client_secret(self) -> str | None:
        return self.ig_app_secret

    # LLM Providers
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    llm_provider: Literal["openai", "gemini"] = "gemini"
    llm_model: str = "gemini-1.5-pro"

    # Email (for reports)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    email_from: str = "noreply@localseo.app"

    # Application URL (for OAuth callbacks, email links)
    app_url: str = "http://localhost:3000"

    # Notification channels
    slack_webhook_url: str | None = None
    kakao_api_token: str | None = None
    sentry_dsn: str | None = None

    # Stripe Price IDs - Plans
    stripe_price_maps_starter_monthly: str | None = None
    stripe_price_maps_starter_yearly: str | None = None
    stripe_price_calls_growth_monthly: str | None = None
    stripe_price_calls_growth_yearly: str | None = None
    stripe_price_competitive_market_monthly: str | None = None
    stripe_price_competitive_market_yearly: str | None = None

    # Legacy self-serve Stripe prices kept for existing subscriptions and internal migrations.
    stripe_price_starter_monthly: str | None = None
    stripe_price_starter_yearly: str | None = None
    stripe_price_pro_monthly: str | None = None
    stripe_price_pro_yearly: str | None = None
    stripe_price_premium_monthly: str | None = None
    stripe_price_premium_yearly: str | None = None
    stripe_price_agency_monthly: str | None = None
    stripe_price_agency_yearly: str | None = None
    
    # Stripe Price IDs - Credit Packages (one-time payments)
    # Leave empty to use inline price_data (no Stripe dashboard pre-setup required).
    stripe_price_credits_50: str | None = None   # 50 credits  $4.99
    stripe_price_credits_100: str | None = None  # 100 credits $8.99
    stripe_price_credits_250: str | None = None  # 250 credits $19.99
    stripe_price_credits_500: str | None = None  # 500 credits $34.99

    # Stripe Price IDs - Add-ons
    stripe_price_addon_mcb: str | None = None       # Missed Call Text Back $29
    stripe_price_addon_rb: str | None = None        # Review Booster $39
    stripe_price_addon_seo: str | None = None       # Website SEO $49
    stripe_price_addon_sar: str | None = None       # Social Auto-Responder $29
    stripe_price_addon_video: str | None = None     # Video Generator $49

    # Twilio (Missed Call Text Back)
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_phone_number: str | None = None

    # SendGrid (Email)
    sendgrid_api_key: str | None = None
    sendgrid_from_email: str | None = None

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug_value(cls, value: bool | str) -> bool:
        """Accept common env-style debug strings without failing settings load."""
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on", "debug", "development", "dev"}:
            return True
        if normalized in {"0", "false", "no", "off", "release", "production", "prod"}:
            return False
        raise ValueError("DEBUG must be a boolean-compatible value")

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure database URL is valid."""
        if not v:
            raise ValueError("DATABASE_URL is required")
        return v

    @field_validator("auth_cookie_path", mode="before")
    @classmethod
    def normalize_auth_cookie_path(cls, value: str | None) -> str:
        """Normalize the refresh-cookie path so proxy deployments can override it safely."""
        if value is None:
            return "/"

        path = str(value).strip()
        if not path or path == "/":
            return "/"

        if not path.startswith("/"):
            path = f"/{path}"

        return path.rstrip("/") or "/"

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.app_env == "prod"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
