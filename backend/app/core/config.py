from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://cci:cci@localhost:5432/cci"
    socrata_app_token: str | None = None
    socrata_timeout: float = Field(default=20, gt=0, le=60)
    socrata_retries: int = Field(default=2, ge=0, le=4)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    capital_markets_timeout: float = Field(default=30, gt=0, le=60)
    capital_markets_retries: int = Field(default=2, ge=0, le=4)
    capital_markets_storage_dir: Path = Path("var/capital-markets")
    capital_markets_max_age_hours: int = Field(default=24, ge=1, le=8760)
    upstream_concurrency: int = Field(default=4, ge=1, le=20)


@lru_cache
def get_settings() -> Settings:
    return Settings()
