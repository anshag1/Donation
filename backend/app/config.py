from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment variables / .env.

    Fields with no default are required — the app fails fast at startup if
    they're missing, rather than surfacing a confusing error later.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"

    database_url: str

    jwt_secret: str
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    frontend_origin: str = "http://localhost:3000"

    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    resend_api_key: str = ""
    resend_from_email: str = "receipts@example.org"

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = ""

    default_org_receipt_prefix: str = "DEMO"

    @property
    def razorpay_configured(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)

    @property
    def razorpay_webhook_configured(self) -> bool:
        return bool(self.razorpay_webhook_secret)

    @property
    def resend_configured(self) -> bool:
        return bool(self.resend_api_key)

    @property
    def supabase_storage_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key and self.supabase_storage_bucket)

    @property
    def is_test(self) -> bool:
        return self.environment == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
