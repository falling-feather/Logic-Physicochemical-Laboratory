from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASTRA_", env_file=".env", extra="ignore")

    app_name: str = "Astra Backend"
    app_version: str = "0.1.0-v6.5"
    environment: str = "development"
    api_prefix: str = "/api"
    api_cache_control: str = "no-store"
    auto_create_tables: bool = False
    session_cookie_name: str = "astra_session"
    session_days: int = 7
    session_last_seen_update_seconds: int = Field(default=300, ge=0)
    password_reset_token_ttl_seconds: int = Field(default=30 * 60, ge=60)
    password_reset_request_cooldown_seconds: int = Field(default=5 * 60, ge=0)
    password_reset_return_token_for_dev: bool = False
    login_max_attempts: int = 5
    login_lockout_seconds: int = 15 * 60
    login_attempt_window_seconds: int = 15 * 60
    audit_log_retention_days: int = Field(default=365, ge=1)
    audit_ip_hash_salt: str = "astra-dev-audit-salt"
    cors_origins: str = "http://127.0.0.1:8766,http://localhost:8766"
    admin_bootstrap_token: str | None = None
    knowledge_snapshot_scheduler_enabled: bool = False
    knowledge_snapshot_scheduler_run_on_start: bool = False
    knowledge_snapshot_scheduler_interval_seconds: int = Field(default=300, ge=30)
    knowledge_snapshot_scheduler_lease_seconds: int = Field(default=3600, ge=60)
    knowledge_snapshot_scheduler_heartbeat_seconds: int = Field(default=120, ge=30)
    knowledge_snapshot_daily_enabled: bool = True
    knowledge_snapshot_daily_hour: int = Field(default=3, ge=0, le=23)
    knowledge_snapshot_weekly_enabled: bool = True
    knowledge_snapshot_weekly_weekday: int = Field(default=0, ge=0, le=6)
    knowledge_snapshot_weekly_hour: int = Field(default=4, ge=0, le=23)
    knowledge_snapshot_retry_attempts: int = Field(default=3, ge=0, le=20)
    database_url: str = Field(
        default="mysql+pymysql://astra:astra@127.0.0.1:3306/astra?charset=utf8mb4",
        description="SQLAlchemy database URL. MySQL is the production target.",
    )

    @property
    def safe_database_url(self) -> str:
        if "://" not in self.database_url or "@" not in self.database_url:
            return self.database_url
        scheme, rest = self.database_url.split("://", 1)
        _, host = rest.rsplit("@", 1)
        return f"{scheme}://***:***@{host}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
