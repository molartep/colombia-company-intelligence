from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://cci:cci@localhost:5432/cci"
    socrata_app_token: str | None = None
    socrata_timeout: float = Field(default=20, gt=0, le=60)
    socrata_retries: int = Field(default=2, ge=0, le=4)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    upstream_concurrency: int = Field(default=4, ge=1, le=20)


@lru_cache
def get_settings() -> Settings:
    return Settings()
