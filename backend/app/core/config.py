from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASTRA_", env_file=".env", extra="ignore")

    app_name: str = "Astra Backend"
    app_version: str = "0.1.0-v6.5"
    environment: str = "development"
    api_prefix: str = "/api"
    auto_create_tables: bool = False
    session_cookie_name: str = "astra_session"
    session_days: int = 7
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
