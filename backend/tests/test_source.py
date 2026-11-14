from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.errors import SourceError
from app.integrations.rues.adapter import RuesDataSource, map_record, source_datetime
from app.integrations.socrata import SocrataClient


@pytest.mark.parametrize("kind", ["nit", "name", "empty"])
async def test_success(record, kind):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=[] if kind == "empty" else [record])

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), headers={"X-App-Token": "synthetic-token"}
    ) as http:
        adapter = RuesDataSource(SocrataClient(http))
        rows = await (
            adapter.search_by_nit("000123456")
            if kind == "nit"
            else adapter.search_by_name("SYNTHETIC")
        )
        assert len(rows) == (0 if kind == "empty" else 1)
        assert seen[0].headers["X-App-Token"] == "synthetic-token"
        assert seen[0].url.params["$limit"] == "20"
        assert seen[0].url.params["$order"] == ":id"
        assert ("nit = " in seen[0].url.params["$where"]) == (kind == "nit")


async def test_quote_and_wildcard_escape():
    seen = []

    def handler(request):
        seen.append(request.url.params["$where"])
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        await RuesDataSource(SocrataClient(http)).search_by_name("O'NEIL_%")
    assert seen == ["replace(upper(razon_social), ' ', '') like '%O''NEIL%'"]


def test_mapping(record):
    mapped = map_record(record)
    assert mapped["nit"] == "000123456"
    assert mapped["primary_ciiu"] == "0011"
    assert "department" not in mapped
    del record["nit"]
    record["numero_identificacion"] = "DO-NOT-SUBSTITUTE"
    assert map_record(record)["nit"] is None
    record["nit"] = "BAD"
    assert map_record(record)["nit"] is None
    assert source_datetime(record["fecha_actualizacion"]).hour == 15
    assert source_datetime("00000000") is None


@pytest.mark.parametrize(
    "payload",
    [{}, {"razon_social": 123}, {"razon_social": "SYNTHETIC", "nit": 123}, {"razon_social": ""}],
)
def test_malformed_record(payload):
    with pytest.raises(SourceError, match="Source record"):
        map_record(payload)


async def test_metadata_schema_change(metadata):
    metadata["columns"] = [c for c in metadata["columns"] if c["fieldName"] != "nit"]
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=metadata))
    ) as http:
        with pytest.raises(SourceError) as exc:
            await RuesDataSource(SocrataClient(http)).metadata()
        assert exc.value.code == "source_schema_changed"


@pytest.mark.parametrize("payload", [{"error": "oops"}, [1], [{"razon_social": 123}]])
async def test_invalid_response(payload):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload))
    ) as http:
        with pytest.raises(SourceError):
            await RuesDataSource(SocrataClient(http)).search_by_nit("000123456")


@pytest.mark.parametrize("status", [429, 500, 502, 503])
async def test_transient_retry(status):
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        return httpx.Response(status if count == 1 else 200, json=[], headers={"Retry-After": "2"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with patch("app.integrations.socrata.asyncio.sleep", new_callable=AsyncMock) as sleep:
            assert await SocrataClient(http).records({"$limit": "1"}) == []
            assert count == 2
            sleep.assert_awaited_once_with(2.0)


async def test_long_retry_after_not_retried_early():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(429, headers={"Retry-After": "120"}))
    ) as http:
        with patch("app.integrations.socrata.asyncio.sleep", new_callable=AsyncMock) as sleep:
            with pytest.raises(SourceError) as exc:
                await SocrataClient(http).records({"$limit": "1"})
            assert exc.value.code == "source_rate_limited"
            sleep.assert_not_awaited()


async def test_invalid_request_no_retry():
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        return httpx.Response(400)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(SourceError):
            await SocrataClient(http).records({"$limit": "1"})
        assert count == 1


async def test_timeout_bounded():
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        raise httpx.ReadTimeout("synthetic timeout")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with patch("app.integrations.socrata.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(SourceError) as exc:
                await SocrataClient(http, retries=1).records({"$limit": "1"})
            assert exc.value.code == "source_timeout"
            assert count == 2


async def test_bounds():
    async with httpx.AsyncClient() as http:
        for params in [{}, {"$limit": "100000"}, {"$limit": "1", "$offset": "90000"}]:
            with pytest.raises(ValueError):
                await SocrataClient(http).records(params)


@pytest.mark.parametrize("query", ["testnorte", "test norte", "TEST  NORTE", "test\tnorte"])
async def test_spacing_insensitive_name_query(record, query):
    seen = []
    row = dict(record, razon_social="TEST NORTE SAS")

    def handler(request):
        seen.append(request)
        if (
            request.url.params["$where"]
            == "replace(upper(razon_social), ' ', '') like '%TESTNORTE%'"
        ):
            return httpx.Response(200, json=[row])
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        rows = await RuesDataSource(SocrataClient(http)).search_by_name(query, limit=2, offset=3)
    assert rows == [row]
    assert len(seen) == 1
    assert seen[0].url.params["$limit"] == "2"
    assert seen[0].url.params["$offset"] == "3"
