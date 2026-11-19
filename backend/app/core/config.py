from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    environment: Literal["development", "production"] = "development"
    public_hostname: str = ""
    allowed_hosts: list[str] = ["*"]
    public_api_docs: bool = True
    admin_import_token: str | None = Field(default=None, min_length=32)
    rate_limits_enabled: bool = False
    search_requests_per_minute: int = Field(default=30, ge=1, le=1000)
    refresh_requests_per_minute: int = Field(default=6, ge=1, le=100)
    refresh_min_interval_seconds: int = Field(default=60, ge=1, le=3600)
    rate_limit_max_entries: int = Field(default=10000, ge=10, le=100000)
    database_url: str = "postgresql+asyncpg://cci:cci@localhost:5432/cci"
    socrata_app_token: str | None = None
    socrata_timeout: float = Field(default=20, gt=0, le=60)
    socrata_retries: int = Field(default=2, ge=0, le=4)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    capital_markets_timeout: float = Field(default=30, gt=0, le=60)
    capital_markets_retries: int = Field(default=2, ge=0, le=4)
    capital_markets_storage_dir: Path = Path("var/capital-markets")
    capital_markets_max_age_hours: int = Field(default=24, ge=1, le=8760)
    bvc_cache_minutes: int = Field(default=15, ge=1, le=1440)
    bvc_page_urls: dict[str, str] = {}
    upstream_concurrency: int = Field(default=4, ge=1, le=20)

    @model_validator(mode="after")
    def validate_production(self) -> Self:
        if self.environment != "production":
            return self
        hostname = self.public_hostname
        if not hostname or any(c in hostname for c in "/:* ") or "." not in hostname:
            raise ValueError("Production requires a public DNS hostname without a scheme or port.")
        if "*" in "".join(self.allowed_hosts) or hostname not in self.allowed_hosts:
            raise ValueError(
                "Production allowed_hosts must explicitly include the public hostname."
            )
        database = urlsplit(self.database_url)
        if database.scheme != "postgresql+asyncpg" or not database.hostname:
            raise ValueError("Production requires a postgresql+asyncpg database URL.")
        if not database.password or len(database.password) < 32:
            raise ValueError(
                "Production requires a generated database password of at least 32 characters."
            )
        if not self.rate_limits_enabled:
            raise ValueError("Production requires request limits.")
        if any(origin != f"https://{hostname}" for origin in self.cors_origins):
            raise ValueError("Production CORS must be empty or limited to the public HTTPS origin.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
