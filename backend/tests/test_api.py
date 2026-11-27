import httpx
import pytest

from app.db.session import get_session
from app.main import app


@pytest.fixture
async def client():
    async def no_db():
        yield None

    app.dependency_overrides[get_session] = no_db
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()


async def test_health(client):
    assert (await client.get("/health")).json() == {"status": "ok"}


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/companies?q=x",
        "/api/v1/companies?q=test&page_size=51",
        "/api/v1/companies?q=test&page=101",
        "/api/v1/companies/not-a-uuid",
        "/api/v1/companies?q=900123456--1",
        "/api/v1/companies?q=%25%25",
    ],
)
async def test_validation(client, path):
    # The adapter dependency must be available, but no outbound call or DB access is needed.
    app.state.rues = None
    response = await client.get(path)
    assert response.status_code == 422
    assert set(response.json()) == {"error"}


async def test_request_limits(client):
    assert (await client.get("/health?" + "q=" + "x" * 8300)).status_code == 414
    assert (await client.post("/health", content="x")).status_code == 405
    assert (await client.request("GET", "/health", content="x")).status_code == 413


async def test_database_failure_is_503(client):
    from unittest.mock import AsyncMock

    from app.core.errors import DatabaseUnavailable

    async def failed_database():
        db = AsyncMock()
        db.execute.side_effect = DatabaseUnavailable("private connection details")
        yield db

    app.dependency_overrides[get_session] = failed_database
    response = await client.get("/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    assert "private connection" not in response.text


async def test_unknown_route_has_consistent_error(client):
    response = await client.get("/api/v1/unknown")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_company_reasoning_refresh_refuses_cross_origin(client):
    response = await client.post(
        "/api/v1/companies/00000000-0000-0000-0000-000000000001/screening/secop/involvement/refresh",
        headers={"Origin": "https://untrusted.example", "Sec-Fetch-Site": "cross-site"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    "origin", ["http://localhost:5174", "http://127.0.0.1:5174", "http://localhost:5173"]
)
async def test_configured_vite_origins_can_refresh_both_sources(client, monkeypatch, origin):
    from unittest.mock import AsyncMock
    from uuid import UUID

    import app.main as main
    from app.core.config import Settings
    from app.schemas.secop import ScreeningView
    from app.services.government_involvement import demo

    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None))
    monkeypatch.setattr(main, "get_company", AsyncMock(return_value=object()))
    monkeypatch.setattr(app.state, "secop", object(), raising=False)
    screening = ScreeningView(
        company_id=UUID("00000000-0000-0000-0000-000000000001"),
        company_name="SYNTHETIC",
        nit="000000001",
        source_id="secop",
        source_url="https://www.datos.gov.co/d/jbjy-vk9h",
        outcome="completed_no_matches",
        cache_ttl_seconds=86400,
    )
    secop_refresh = AsyncMock(return_value=screening)
    reasoning_refresh = AsyncMock(return_value=demo())
    monkeypatch.setattr(main.secop, "refresh", secop_refresh)
    monkeypatch.setattr(main.government_involvement, "company_view", reasoning_refresh)
    base = "/api/v1/companies/00000000-0000-0000-0000-000000000001/screening/secop"
    for endpoint in ["/refresh", "/involvement/refresh"]:
        response = await client.post(
            base + endpoint, headers={"Origin": origin, "Sec-Fetch-Site": "same-origin"}
        )
        assert response.status_code == 200
    secop_refresh.assert_awaited_once()
    reasoning_refresh.assert_awaited_once()


@pytest.mark.parametrize("endpoint", ["/refresh", "/involvement/refresh"])
async def test_refresh_preserves_retry_after_header(client, monkeypatch, endpoint):
    from unittest.mock import AsyncMock

    from fastapi import HTTPException

    import app.main as main

    monkeypatch.setattr(main, "get_company", AsyncMock(return_value=object()))
    monkeypatch.setattr(app.state, "secop", object(), raising=False)
    failure = AsyncMock(
        side_effect=HTTPException(429, "Wait before refreshing.", headers={"Retry-After": "15"})
    )
    monkeypatch.setattr(main.secop, "refresh", failure)
    monkeypatch.setattr(main.government_involvement, "company_view", failure)
    response = await client.post(
        "/api/v1/companies/00000000-0000-0000-0000-000000000001/screening/secop" + endpoint
    )
    assert response.status_code == 429 and response.headers["Retry-After"] == "15"


@pytest.mark.parametrize("endpoint", ["/refresh", "/involvement/refresh"])
async def test_unconfigured_frontend_origin_stays_rejected(client, endpoint):
    response = await client.post(
        "/api/v1/companies/00000000-0000-0000-0000-000000000001/screening/secop" + endpoint,
        headers={"Origin": "http://localhost:9999"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize("months", ["0", "121", "-1", "1.5", "unknown"])
@pytest.mark.parametrize("method", ["GET", "POST"])
async def test_company_lookback_range_validation(client, months, method):
    path = "/api/v1/companies/00000000-0000-0000-0000-000000000001/screening/secop/involvement"
    if method == "POST":
        path += "/refresh"
    response = await client.request(method, path, params={"lookback_months": months})
    assert response.status_code == 422
