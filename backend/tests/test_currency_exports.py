import csv
import io
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi import HTTPException

from app.core.errors import SourceError
from app.integrations.socrata import SocrataClient
from app.services.currency import ReferenceRates, positive_rate, presentation_rate, usd
from app.services.exports import ISSUER_FIELDS, converted, download, project


@pytest.mark.parametrize(
    "value", ["0", "-1", "NaN", "Infinity", "1e4", "4,000", " 4000", "1.0000000000001"]
)
def test_invalid_rates(value):
    with pytest.raises(ValueError):
        positive_rate(value)


def test_precision_and_half_even():
    assert usd("999999999999999999.123456", "4000") == "250000000000000.00"
    assert usd("4000.02", "4000") == "1.00"
    assert usd("900719925474099312345678.12", "1") == "900719925474099312345678.12"
    assert usd("0.025", "1") == "0.02"
    assert usd("0.035", "1") == "0.04"
    assert usd("-0.035", "1") == "-0.04"
    assert positive_rate("0.000000000001") == Decimal("0.000000000001")


def test_csv_unicode_escaping_injection_and_json_originals():
    values = [
        '=HYPERLINK("bad")',
        " +1",
        "\t@bad",
        "-2",
        'Árbol, "Ñ"\n東京',
        "000123456",
        "999999999999999999.123456",
    ]
    document = {
        "schema_version": "1.0",
        "warnings": ["stale"],
        "rows": [{"value": v} for v in values],
    }
    response = download(document, "csv", "test")
    rows = list(csv.DictReader(io.StringIO(response.body.decode("utf-8-sig"))))
    assert [r["value"] for r in rows] == ["'" + v for v in values[:4]] + values[4:]
    assert json.loads(rows[0]["metadata_json"])["warnings"] == ["stale"]
    assert json.loads(download(document, "json", "test").body)["rows"] == document["rows"]
    empty = download({"rows": [], "warnings": ["no matches"]}, "csv", "test")
    assert "no matches" in empty.body.decode()


def test_export_limits_and_sensitive_projection():
    with pytest.raises(HTTPException) as error:
        download({"rows": [{}] * 1001}, "json", "test")
    assert error.value.status_code == 413
    with pytest.raises(HTTPException):
        download({"rows": [{"description": "x" * (5 * 1024 * 1024)}]}, "json", "test")
    safe = project(
        {
            "issuer_name": "Árbol",
            "contacts": {"phone": "SECRET"},
            "raw_payload": "SECRET",
            "administration": "SECRET",
        },
        ISSUER_FIELDS,
    )
    assert "SECRET" not in json.dumps(safe)


async def test_provider_weekend_validity_cache_failure_and_manual():
    today = datetime.now(ZoneInfo("America/Bogota")).date()
    client = AsyncMock()
    client.get.return_value = [
        {
            "valor": "4000.1234",
            "unidad": "COP",
            "vigenciadesde": (today - timedelta(days=2)).isoformat() + "T00:00:00.000",
            "vigenciahasta": today.isoformat() + "T00:00:00.000",
        }
    ]
    provider = ReferenceRates(client)
    first = await provider.get()
    assert not first.stale and not first.manual
    await provider.get()
    assert client.get.await_count == 1
    provider.next_check = 0
    client.get.side_effect = SourceError("source_timeout", "test")
    failed = await provider.get()
    assert failed.stale and failed.provider_failed and failed.retrieved_at == first.retrieved_at
    with pytest.raises(SourceError):
        await presentation_rate(provider, "reference", None, None)
    manual = await presentation_rate(provider, "manual", "4000.1234", today)
    assert manual.manual and manual.source_url is None
    original = {"value": "999999999999999999.123456", "currency": "COP"}
    result = converted(original, "value", manual)
    assert result["value"] == original["value"] and "presentation_usd" in result
    assert "presentation_usd" not in original
    assert "presentation_usd" not in converted({"value": "42", "currency": None}, "value", manual)


@pytest.mark.parametrize("row", [None, [], [{"valor": "-1"}], [{"valor": "4000", "unidad": "USD"}]])
async def test_provider_invalid_or_absent_data(row):
    client = AsyncMock()
    client.get.return_value = row
    with pytest.raises(SourceError):
        await ReferenceRates(client).get()


async def test_provider_expired_interval():
    today = datetime.now(UTC).date()
    client = AsyncMock()
    client.get.return_value = [
        {
            "valor": "4000",
            "unidad": "COP",
            "vigenciadesde": (today - timedelta(days=10)).isoformat(),
            "vigenciahasta": (today - timedelta(days=5)).isoformat(),
        }
    ]
    assert (await ReferenceRates(client).get()).stale


async def test_fixed_host_transport_bounds():
    async def handler(request):
        assert request.url.host == "www.datos.gov.co"
        assert request.url.params["$limit"] == "1"
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await SocrataClient(client).get("/resource/32sa-8pi3.json", {"$limit": "1"}) == []


async def test_contract_export_filters_snapshot_and_states(monkeypatch):
    from types import SimpleNamespace
    from uuid import uuid4

    from app.api import exports as api
    from app.schemas.secop import ContractPage

    company_id, run_id = uuid4(), uuid4()
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(id=company_id)
    monkeypatch.setattr(
        api,
        "profile",
        AsyncMock(
            return_value=SimpleNamespace(
                model_dump=lambda **kw: {
                    "id": str(company_id),
                    "legal_name": "Árbol",
                    "nit": "000123456",
                }
            )
        ),
    )
    screening = SimpleNamespace(
        summary=True,
        run_id=run_id,
        warnings=["stale"],
        model_dump=lambda **kw: {"outcome": "stale", "run_id": str(run_id)},
    )
    monkeypatch.setattr(api.secop, "view", AsyncMock(return_value=screening))
    query = AsyncMock(
        return_value=ContractPage(
            items=[], page=1, page_size=1001, total=0, has_more=False, run_id=run_id
        )
    )
    monkeypatch.setattr(api.secop, "contracts_page", query)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(reference_rates=None)))
    options = api.ExportOptions(
        run_id=run_id,
        raw_status="En ejecución",
        entity="Árbol",
        missing_signature_date=True,
        modality="Original",
        q="Ñ",
        sort="value",
        direction="asc",
    )
    response = await api.export_company(company_id, "contracts", request, session, options)
    document = json.loads(response.body)
    assert document["screening"]["outcome"] == "stale"
    assert document["rows"] == [] and document["filtered_total"] == 0
    assert query.call_args.kwargs == dict(
        run_id=run_id,
        status=None,
        raw_status="En ejecución",
        entity="Árbol",
        year=None,
        missing_signature_date=True,
        modality="Original",
        q="Ñ",
        sort="value",
        direction="asc",
    )
    query.return_value = ContractPage(
        items=[], page=1, page_size=1001, total=1001, has_more=False, run_id=run_id
    )
    with pytest.raises(HTTPException) as limit:
        await api.export_company(company_id, "contracts", request, session, options)
    assert limit.value.status_code == 413
    options.run_id = uuid4()
    with pytest.raises(HTTPException) as changed:
        await api.export_company(company_id, "contracts", request, session, options)
    assert changed.value.status_code == 409
    screening.summary = None
    with pytest.raises(HTTPException) as unavailable:
        await api.export_company(company_id, "contracts", request, session, options)
    assert unavailable.value.status_code == 409


async def test_export_http_validation_and_rate_route(monkeypatch):
    from uuid import uuid4

    from app.db.session import get_session
    from app.main import app

    async def no_db():
        yield None

    provider = AsyncMock()
    today = datetime.now(ZoneInfo("America/Bogota")).date()
    from app.services.currency import Rate

    provider.get.return_value = Rate(
        cop_per_usd="4000.1234",
        source="SFC",
        source_url="https://www.datos.gov.co/d/32sa-8pi3",
        effective_date=today,
        effective_until=today,
        retrieved_at=datetime.now(UTC),
    )
    monkeypatch.setattr(app.state, "reference_rates", provider, raising=False)
    app.dependency_overrides[get_session] = no_db
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for suffix in [
                "format=pdf",
                "sort=random",
                "fx_mode=guess",
                "year=1800",
                "run_id=bad",
                "manual_rate=" + "1" * 26,
            ]:
                response = await client.get(
                    f"/api/v1/companies/{uuid4()}/exports/contracts?{suffix}"
                )
                assert response.status_code == 422
            response = await client.get("/api/v1/presentation/usd-rate")
            assert response.status_code == 200
            assert response.json()["cop_per_usd"] == "4000.1234"
            assert response.json()["manual"] is False
    finally:
        app.dependency_overrides.clear()
