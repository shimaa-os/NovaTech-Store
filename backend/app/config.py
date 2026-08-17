from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./novatech.db"
    redis_url: str = "redis://127.0.0.1:6379/0"
    app_origin: str = "http://127.0.0.1:8000"
    allowed_hosts: list[str] = Field(default_factory=lambda: ["127.0.0.1", "localhost", "testserver"])
    session_secret: str = "development-session-secret-change-me"
    csrf_secret: str = "development-csrf-secret-change-me"
    otp_secret: str = "development-otp-secret-change-me"
    mfa_encryption_key: str = ""
    cookie_secure: bool = False
    session_idle_seconds: int = 30 * 60
    session_absolute_seconds: int = 12 * 60 * 60
    otp_ttl_seconds: int = 10 * 60
    otp_resend_cooldown_seconds: int = 60
    otp_max_attempts: int = 5
    email_from: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True
    s3_endpoint_url: str = ""
    s3_region: str = "auto"
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    asset_origin: str = ""
    frontend_dir: Path = PROJECT_ROOT / "frontend"

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @field_validator("app_origin")
    @classmethod
    def strip_origin(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def session_cookie_name(self) -> str:
        return "__Host-nova_session" if self.cookie_secure else "nova_session"

    @property
    def csrf_cookie_name(self) -> str:
        return "__Host-nova_csrf" if self.cookie_secure else "nova_csrf"

    def validate_production(self) -> None:
        if self.environment != "production":
            return
        weak = (
            len(self.session_secret) < 32
            or len(self.csrf_secret) < 32
            or len(self.otp_secret) < 32
        )
        if weak or not self.cookie_secure or not self.database_url.startswith("postgresql+"):
            raise RuntimeError("Production secrets, secure cookies, and PostgreSQL are required")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production()
    return settings

