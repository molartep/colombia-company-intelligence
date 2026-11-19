from unittest.mock import AsyncMock

import httpx
import pytest
from starlette.requests import Request

from app.api import operations
from app.core.config import Settings
from app.core.errors import SourceError
from app.main import app


def operator_request(host="localhost", client="127.0.0.1", origin="http://localhost", token=""):
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": operations.IMPORT_PATH,
            "query_string": b"",
            "scheme": "http",
            "server": (host, 80),
            "client": (client, 1234),
            "headers": [
                (b"host", host.encode()),
                (b"origin", origin.encode()),
                (b"x-cci-admin-token", token.encode()),
            ],
        }
    )


def test_import_requires_same_origin_and_local_client_or_explicit_key(monkeypatch):
    config = Settings(_env_file=None)
    monkeypatch.setattr(operations, "get_settings", lambda: config)
    operations.authorize_import(operator_request())
    operations.authorize_import(operator_request(origin="http://127.0.0.1:5173"))
    for request in (
        operator_request(origin="http://evil.example"),
        operator_request(client="203.0.113.1"),
        operator_request(host="evil.example", origin="http://evil.example"),
        operator_request(origin="null"),
    ):
        with pytest.raises(SourceError) as error:
            operations.authorize_import(request)
        assert error.value.status == 403
    config.admin_import_token = "a" * 32
    operations.authorize_import(operator_request(client="203.0.113.1", token="a" * 32))


def test_production_never_treats_proxy_loopback_as_local_operator(monkeypatch):
    config = Settings.model_construct(
        environment="production", public_hostname="cci.example.org", admin_import_token="a" * 32
    )
    monkeypatch.setattr(operations, "get_settings", lambda: config)
    with pytest.raises(SourceError):
        operations.authorize_import(operator_request(origin="https://cci.example.org"))
    operations.authorize_import(operator_request(origin="https://cci.example.org", token="a" * 32))


async def test_cross_origin_import_never_calls_downloader(monkeypatch):
    download = AsyncMock()
    monkeypatch.setattr(operations, "download_directory", download)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        response = await client.post(
            operations.IMPORT_PATH, headers={"Origin": "http://evil.example"}
        )
    assert response.status_code == 403
    download.assert_not_awaited()


async def test_import_size_rejected_before_downloading(monkeypatch):
    download = AsyncMock()
    monkeypatch.setattr(operations, "download_directory", download)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        response = await client.post(
            operations.IMPORT_PATH,
            headers={"Origin": "http://localhost", "Content-Length": str(operations.MAX_BYTES + 1)},
        )
    assert response.status_code == 413
    download.assert_not_awaited()


@pytest.mark.parametrize("first_download_time", [0.0, 10.0, 59.0, 1000.0])
async def test_download_cooldown_allows_first_import_at_any_clock_origin(
    monkeypatch, first_download_time
):
    import asyncio
    from datetime import UTC, datetime
    from types import SimpleNamespace
    from uuid import uuid4

    now = [first_download_time]
    monkeypatch.setattr(operations, "get_settings", lambda: Settings(_env_file=None))
    monkeypatch.setattr(operations, "time", SimpleNamespace(monotonic=lambda: now[0]))
    monkeypatch.setattr(operations, "_last_download", None)
    monkeypatch.setattr(operations, "_import_lock", asyncio.Lock())
    download = AsyncMock(return_value=b"synthetic XLSX")
    ingest = AsyncMock(
        return_value=SimpleNamespace(
            id=uuid4(),
            record_count=1,
            retrieved_at=datetime.now(UTC),
            content_hash="synthetic-hash",
        )
    )
    monkeypatch.setattr(operations, "download_directory", download)
    monkeypatch.setattr(operations, "ingest_issuers", ingest)
    session = AsyncMock()
    assert (await operations.import_directory(operator_request(), session)).record_count == 1
    assert operations._last_download == first_download_time
    assert download.await_count == 1

    for offset in (0.0, 59.999):
        now[0] = first_download_time + offset
        with pytest.raises(SourceError) as exc:
            await operations.import_directory(operator_request(), session)
        assert exc.value.code == "import_cooldown" and exc.value.status == 429
    assert download.await_count == 1

    now[0] = first_download_time + 60
    assert (await operations.import_directory(operator_request(), session)).record_count == 1
    assert download.await_count == 2 and ingest.await_count == 2
