import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import SourceError
from app.integrations.rues.adapter import RuesDataSource
from app.integrations.socrata import SocrataClient
from app.schemas.api import SearchPage
from app.services import companies


def test_sixty_second_default_and_validation():
    assert Settings(_env_file=None).socrata_timeout == 60
    for value in (0, -1, 61, float("inf")):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, socrata_timeout=value)


def search_setup(monkeypatch, cached):
    session = AsyncMock()
    session.scalars.return_value = [object()] if cached else []
    source = SimpleNamespace(enabled=True, availability="available")
    monkeypatch.setattr(companies, "ensure_source", AsyncMock(return_value=source))
    monkeypatch.setattr(companies, "get_settings", lambda: SimpleNamespace(socrata_timeout=0.02))
    serializer = AsyncMock(
        side_effect=lambda *a: SearchPage(
            items=[], page=a[4], page_size=a[5], has_more=a[6], stale=a[7], warning=a[8]
        )
    )
    monkeypatch.setattr(companies, "serialize_search", serializer)
    persist = AsyncMock()
    monkeypatch.setattr(companies, "persist", persist)
    bvc = AsyncMock()
    monkeypatch.setattr(companies, "registration_nits", bvc)
    return session, source, serializer, persist, bvc


@pytest.mark.parametrize("phase", ["metadata", "query", "retry"])
@pytest.mark.parametrize("cached", [False, True])
async def test_deadline_cancels_pending_network_and_uses_only_available_cache(
    monkeypatch, phase, cached
):
    session, source, serializer, persist, bvc = search_setup(monkeypatch, cached)
    cancelled = asyncio.Event()

    async def blocked(*args, **kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    adapter = AsyncMock(spec=RuesDataSource)
    adapter.metadata.return_value = {}
    if phase == "metadata":
        adapter.metadata.side_effect = blocked
    else:
        adapter.search_by_name.side_effect = blocked
    attempts = []

    async def retry_handler(request):
        attempts.append(request)
        return httpx.Response(503, headers={"Retry-After": "2"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(retry_handler)) as http:
        if phase == "retry":
            # Exercise real retry backoff within the shared RUES deadline.
            adapter = RuesDataSource(SocrataClient(http, retries=2))
        if cached:
            result = await companies.search_companies(
                session, adapter, "Thomas greg", None, 1, 20, securities_retriever=AsyncMock()
            )
            assert result.stale and result.warning == companies.RUES_TIMEOUT_WARNING
            serializer.assert_awaited_once()
        else:
            with pytest.raises(SourceError) as failure:
                await companies.search_companies(session, adapter, "Thomas greg", None, 1, 20)
            assert failure.value.code == "source_timeout" and failure.value.status == 503
            serializer.assert_not_awaited()
    assert source.availability == "failed_to_retrieve"
    persist.assert_not_awaited()
    bvc.assert_not_awaited()
    if phase == "retry":
        assert len(attempts) == 1  # Deadline prevents waiting/retrying for multiple full windows.
    else:
        assert cancelled.is_set()
    if phase == "metadata":
        adapter.search_by_name.assert_not_awaited()


async def test_success_is_fresh_and_external_cancellation_is_not_an_outage(monkeypatch):
    session, source, serializer, persist, bvc = search_setup(monkeypatch, True)
    adapter = AsyncMock(spec=RuesDataSource)
    adapter.metadata.return_value = {}
    adapter.search_by_name.return_value = []
    adapter.search_by_nit.return_value = []
    result = await companies.search_companies(
        session, adapter, "000123456", companies.Nit("000123456", None), 1, 20
    )
    # Use a NIT to avoid the separate normalized-name candidate recovery on empty results.
    adapter.search_by_nit.assert_awaited_once()
    assert not result.stale
    serializer.reset_mock()
    adapter.metadata.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await companies.search_companies(session, adapter, "Thomas greg", None, 1, 20)
    serializer.assert_not_awaited()
    assert source.availability == "available"
    bvc.assert_not_awaited()


async def test_non_timeout_transport_failure_has_distinct_code_and_safe_fallback(monkeypatch):
    session, source, serializer, persist, bvc = search_setup(monkeypatch, True)
    adapter = AsyncMock(spec=RuesDataSource)
    adapter.metadata.side_effect = SourceError("source_unavailable", "Synthetic connection failure")
    result = await companies.search_companies(session, adapter, "Thomas greg", None, 1, 20)
    assert result.stale and result.warning == companies.RUES_UNAVAILABLE_WARNING
    assert "timeout" not in result.warning
    persist.assert_not_awaited()


@pytest.mark.parametrize(
    "exception,expected",
    [
        (httpx.ReadTimeout, "source_timeout"),
        (httpx.ConnectTimeout, "source_timeout"),
        (httpx.ConnectError, "source_unavailable"),
        (httpx.RemoteProtocolError, "source_unavailable"),
    ],
)
async def test_transport_errors_are_classified_without_mislabeling_connections(exception, expected):
    def handler(request):
        raise exception("Synthetic private network detail")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(SourceError) as failure:
            await SocrataClient(http, retries=0).records({"$limit": "1"})
    assert failure.value.code == expected
    assert "private" not in failure.value.message
