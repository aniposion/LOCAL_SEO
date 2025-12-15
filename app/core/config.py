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

    # Database
    database_url: str = Field(
        default="sqlite:///./local_seo.db"
    )

    # JWT
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # AWS
    aws_region: str = "us-east-1"
    s3_bucket: str = "seo-optimizer-reports"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    # Stripe
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None

    # Google Business Profile
    gbp_api_key: str | None = None
    gbp_client_id: str | None = None
    gbp_client_secret: str | None = None

    # Instagram
    ig_app_id: str | None = None
    ig_app_secret: str | None = None

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

    # Stripe Price IDs
    stripe_price_starter_monthly: str | None = None
    stripe_price_starter_yearly: str | None = None
    stripe_price_pro_monthly: str | None = None
    stripe_price_pro_yearly: str | None = None
    stripe_price_agency_monthly: str | None = None
    stripe_price_agency_yearly: str | None = None

    # Twilio (Missed Call Text Back)
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_phone_number: str | None = None

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure database URL is valid."""
        if not v:
            raise ValueError("DATABASE_URL is required")
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.app_env == "prod"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
