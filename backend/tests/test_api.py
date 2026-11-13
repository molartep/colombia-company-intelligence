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
    assert (await client.get("/health?" + "q=" + "x" * 2100)).status_code == 414
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
