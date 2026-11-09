"""Environment-based configuration.

All secrets come from the environment. Provider secret keys are only ever read by
the backend and are never serialised into API responses.
"""

from enum import StrEnum
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class PaymentProviderName(StrEnum):
    MOCK = "mock"
    MOYASAR = "moyasar"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True)

    environment: Environment = Environment.DEVELOPMENT
    app_name: str = "Saudi Multi-Vendor Marketplace"
    log_level: str = "INFO"
    log_json: bool = True

    database_url: str = "postgresql+asyncpg://marketplace:marketplace@localhost:55432/marketplace"
    redis_url: str = "redis://localhost:56379/0"

    public_api_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    jwt_secret: SecretStr = SecretStr("change-me-development-only-secret-key-32b")
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 60 * 60 * 24 * 30
    email_token_ttl_seconds: int = 60 * 60 * 24
    password_reset_ttl_seconds: int = 60 * 60
    cookie_secure: bool = False
    cookie_domain: str | None = None

    rate_limit_enabled: bool = True
    auth_rate_limit_per_minute: int = 10

    upload_dir: str = "var/uploads"
    upload_max_bytes: int = 5 * 1024 * 1024
    media_url_prefix: str = "/media"

    # Checkout
    inventory_reservation_minutes: int = 30
    maintenance_interval_seconds: int = 60
    run_maintenance_loop: bool = True

    # Payments
    payment_provider: PaymentProviderName = PaymentProviderName.MOCK
    mock_webhook_secret: SecretStr = SecretStr("mock-webhook-secret-development-only")
    mock_auto_activate_merchants: bool = True

    moyasar_api_base: str = "https://api.moyasar.com/v1"
    moyasar_platform_api_base: str = "https://apimig.moyasar.com/v1"
    moyasar_secret_key: SecretStr | None = None
    moyasar_platform_api_key: SecretStr | None = None
    moyasar_webhook_secret: SecretStr | None = None  # shared secret of the payments webhook
    moyasar_platform_webhook_secret: SecretStr | None = None  # shared secret of the platform webhook
    moyasar_platform_recipient_id: str | None = None
    # Splitting "is not enabled by default for all platforms" (Moyasar platform docs).
    # Must only be switched on after Moyasar confirms it for this platform account.
    moyasar_splits_enabled: bool = False
    moyasar_live: bool = False
    # Required by `POST /merchants` (Platform API). The fee schedule is a commercial
    # agreement with Moyasar, so it is configuration (JSON), never a code default.
    moyasar_enabled_schemes: list[Literal["mada", "visa", "master"]] = Field(
        default_factory=lambda: list[Literal["mada", "visa", "master"]](["mada", "visa", "master"])
    )
    moyasar_merchant_fees: dict[str, float | bool] | None = None

    # Email (transactional email is optional; when unset, emails are logged only)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str = "no-reply@marketplace.local"
    smtp_starttls: bool = True

    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    @property
    def mock_payments_enabled(self) -> bool:
        return self.payment_provider == PaymentProviderName.MOCK

    @model_validator(mode="after")
    def _guard_production(self) -> "Settings":
        if self.environment == Environment.PRODUCTION:
            if self.payment_provider == PaymentProviderName.MOCK:
                raise ValueError("The mock payment provider must never be used in production.")
            if "change-me" in self.jwt_secret.get_secret_value():
                raise ValueError("JWT_SECRET must be set in production.")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production.")
        if self.payment_provider == PaymentProviderName.MOYASAR:
            missing = [
                name
                for name, value in (
                    ("MOYASAR_SECRET_KEY", self.moyasar_secret_key),
                    ("MOYASAR_WEBHOOK_SECRET", self.moyasar_webhook_secret),
                )
                if value is None
            ]
            if missing:
                raise ValueError(f"Missing Moyasar configuration: {', '.join(missing)}")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
