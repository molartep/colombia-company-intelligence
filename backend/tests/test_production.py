from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError
from starlette.requests import Request

from app.core.config import Settings
from app.core.rate_limits import Bucket, RequestLimiter


def settings(**overrides):
    return Settings(_env_file=None, **overrides)


def request(path, client="192.0.2.1", query=""):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "query_string": query.encode(),
            "headers": [],
            "client": (client, 1234),
            "server": ("test", 80),
            "scheme": "http",
        }
    )


def production_settings(**overrides):
    values = dict(
        environment="production",
        public_hostname="companies.example.org",
        allowed_hosts=["companies.example.org", "localhost"],
        cors_origins=[],
        rate_limits_enabled=True,
        database_url=f"postgresql+asyncpg://cci:{'a' * 64}@db:5432/cci",
    )
    values.update(overrides)
    return settings(**values)


def test_production_requires_safe_configuration():
    assert production_settings().environment == "production"
    for override in (
        {"database_url": "postgresql+asyncpg://cci:cci@db:5432/cci"},
        {"allowed_hosts": ["*"]},
        {"rate_limits_enabled": False},
        {"cors_origins": ["http://localhost:5173"]},
        {"public_hostname": "https://companies.example.org"},
    ):
        with pytest.raises(ValidationError):
            production_settings(**override)


def test_search_windows_and_clients():
    now = [100.0]
    limiter = RequestLimiter(
        settings(rate_limits_enabled=True, search_requests_per_minute=2), clock=lambda: now[0]
    )
    path = "/api/v1/companies"
    assert limiter.check(request(path)) == 0
    assert limiter.check(request(path)) == 0
    assert limiter.check(request(path)) == 60
    assert limiter.check(request(path, client="192.0.2.2")) == 0
    now[0] += 61
    assert limiter.check(request(path)) == 0


def test_refresh_cooldown_shared_across_clients_sources_and_boolean_spellings():
    limiter = RequestLimiter(settings(rate_limits_enabled=True))
    company = uuid4()
    path = f"/api/v1/companies/{company}/capital-markets"
    assert (
        limiter.check(request(path, query="refresh=true&refresh_source=sfc_rnve_issuer_details"))
        == 0
    )
    assert limiter.check(request(path, client="192.0.2.2", query="refresh=y")) > 0
    assert (
        limiter.check(request(f"/api/v1/companies/{str(company).upper()}", query="refresh=1")) > 0
    )
    assert limiter.check(request(path)) == 0  # Cached reads remain available.


def test_limiter_memory_is_bounded_and_full_table_fails_closed():
    now = [100.0]
    limiter = RequestLimiter(
        settings(rate_limits_enabled=True, rate_limit_max_entries=10), clock=lambda: now[0]
    )
    for i in range(20):
        limiter.check(request("/api/v1/sources", client=f"192.0.2.{i}"))
    assert len(limiter.buckets) == 10
    assert limiter.check(request("/api/v1/sources", client="203.0.113.1")) > 0
    assert limiter.check(request("/health")) == 0
    now[0] += 61
    assert limiter.check(request("/api/v1/sources", client="203.0.113.1")) == 0


async def test_rate_limit_http_contract(monkeypatch):
    import app.main as main

    limiter = RequestLimiter(settings(rate_limits_enabled=True, search_requests_per_minute=1))
    # Use parameter catalog to avoid any DB or source calls; exhaust the general API window.
    limiter.buckets[("api", "127.0.0.1")] = Bucket(limiter.clock() + 60, 120)
    monkeypatch.setattr(main, "limiter", limiter)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/parameters")
    assert response.status_code == 429
    assert 1 <= int(response.headers["Retry-After"]) <= 60
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["error"]["code"] == "rate_limited"
