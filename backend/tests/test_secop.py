import copy
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.errors import SourceError
from app.integrations.secop.adapter import API_PATH, META_PATH, SecopSource, supplier_where
from app.integrations.secop.normalize import (
    aggregate,
    event_date,
    money,
    source_link,
    status,
    supplier_matches,
    verified_contracts,
)
from app.integrations.socrata import SocrataClient

NOW = datetime(2026, 11, 18, tzinfo=UTC)
NIT = "000123456"
DV = "7"


@pytest.fixture
def secop_row():
    return {
        "source_row_id": "row-1",
        "id_contrato": "CO1.PCCNTR.SYNTHETIC",
        "proceso_de_compra": "CO1.SYNTHETIC",
        "documento_proveedor": NIT,
        "tipodocproveedor": "NIT",
        "es_grupo": "No",
        "nombre_entidad": "SYNTHETIC BUYER",
        "nit_entidad": "899999999",
        "valor_del_contrato": "100.01",
        "estado_contrato": "En ejecución",
        "fecha_de_firma": "2025-03-01T00:00:00.000",
        "ultima_actualizacion": "2026-01-01T00:00:00.000",
        "departamento": "Bogotá",
        "modalidad_de_contratacion": "Licitación pública",
        "urlproceso": {
            "url": "https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUID=SYNTHETIC"
        },
    }


@pytest.fixture
def secop_metadata():
    return json.loads(
        (Path(__file__).parents[2] / "docs/discovery/secop-metadata.json").read_text()
    )


@pytest.mark.parametrize(
    "identifier,kind,group,match",
    [
        (NIT, "NIT", "No", True),
        ("000.123.456-7", "NIT", "No", True),
        ("000 123 456 - 7", "nit", "No", True),
        (NIT + "7", "NIT", "No", True),
        ("0001234568", "NIT", "No", False),
        ("0.001.234.567", "NIT", "No", True),
        ("00012345678", "NIT", "No", False),
        ("00123456", "NIT", "No", False),
        ("00012345-6", "NIT", "No", False),
        (NIT + "-8", "NIT", "No", False),
        ("999123456", "NIT", "No", False),
        ("123456", "NIT", "No", False),
        (NIT, "Cédula de Ciudadanía", "No", False),
        (NIT, "NIT", "Si", False),
        (NIT, "NIT", "", False),
        ("SYNTHETIC COMPANY", "NIT", "No", False),
        ("000.12.3456", "NIT", "No", False),
    ],
)
def test_supplier_identity(secop_row, identifier, kind, group, match):
    assert (
        supplier_matches(
            dict(secop_row, documento_proveedor=identifier, tipodocproveedor=kind, es_grupo=group),
            NIT,
            DV,
        )
        is match
    )


def test_buyer_never_matches_and_names_do_not_match(secop_row):
    row = dict(
        secop_row,
        documento_proveedor="999999999",
        nit_entidad=NIT,
        proveedor_adjudicado="SYNTHETIC COMPANY",
    )
    assert not supplier_matches(row, NIT, DV)
    assert not supplier_matches(dict(secop_row, documento_proveedor=NIT + "-7"), NIT, None)
    where = supplier_where(NIT, DV)
    assert "nit_entidad" not in where and "proveedor_adjudicado" not in where
    assert "like" not in where and "documento_proveedor in" in where
    assert "'000.123.456-7'" in where
    assert "'0001234567'" in where
    assert "'0001234568'" not in where
    assert not supplier_matches(dict(secop_row, documento_proveedor=NIT + DV), NIT, None)
    with pytest.raises(ValueError):
        supplier_where("12345' OR 1=1", DV)


def test_dedup_latest_conflicting_and_missing_dates(secop_row):
    newer = dict(
        secop_row,
        source_row_id="row-2",
        ultima_actualizacion="2026-02-01T00:00:00",
        valor_del_contrato="200.02",
    )
    result, excluded = verified_contracts(
        [secop_row, newer, dict(newer, source_row_id="row-3")], NIT, DV, NOW
    )
    assert len(result) == 1 and result[0][0].value == Decimal("200.02") and not excluded
    result, excluded = verified_contracts(
        [newer, dict(newer, valor_del_contrato="300")], NIT, DV, NOW
    )
    assert not result and excluded == 1
    result, excluded = verified_contracts(
        [newer, dict(secop_row, ultima_actualizacion=None)], NIT, DV, NOW
    )
    assert not result and excluded == 1


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("0", Decimal(0)),
        ("0.10", Decimal("0.10")),
        ("999999999999999999999999.12", Decimal("999999999999999999999999.12")),
        (None, None),
        ("NaN", None),
        ("Infinity", None),
        ("-1", None),
        ("1,200", None),
        ("0.0000001", None),
    ],
)
def test_money(raw, expected):
    assert money(raw) == expected


def test_decimal_currency_annual_buyers_and_summary(secop_row):
    contract = verified_contracts([secop_row], NIT, DV, NOW)[0][0][0]
    second = contract.model_copy(
        update={"contract_id": "second", "value": Decimal("0.02"), "signature_date": None}
    )
    result = aggregate([contract, second])
    assert (
        result.total_contracts == 2
        and result.total_values == {"COP": Decimal("100.03")}
        and result.unknown_currency_contracts == 0
    )
    assert contract.currency == "COP" and contract.currency_basis == "application_policy"
    assert result.distinct_buyers == 1 and result.latest_signature_date.isoformat() == "2025-03-01"
    assert {g.label: g.count for g in result.annual} == {"2025": 1, "Sin fecha de firma": 1}
    assert result.top_buyers[0].count == 2
    cop = contract.model_copy(update={"currency": "COP", "value": Decimal("0.1")})
    usd = second.model_copy(update={"currency": "USD", "value": Decimal("0.02")})
    total = aggregate([cop, cop.model_copy(update={"value": Decimal("0.2")}), usd])
    assert total.total_values == {"COP": Decimal("0.3"), "USD": Decimal("0.02")}
    assert total.monetary_contracts == 3
    assert "2 contratos únicos" in result.executive_summary
    assert aggregate([]).total_contracts == 0


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("En ejecución", "in_execution"),
        ("Cerrado", "closed"),
        ("terminado", "terminated"),
        (None, "other"),
        ("Unknown", "other"),
    ],
)
def test_status(raw, expected):
    assert status(raw) == expected


def test_dates_and_source_links(secop_row):
    assert event_date("2025-01-01T23:30:00").isoformat() == "2025-01-01"
    assert event_date("2025-02-30") is None and event_date(None) is None
    assert source_link(secop_row)[1] == "Proceso oficial SECOP II"
    for value in [
        "javascript:alert(1)",
        "https://evil.test/Public/1",
        "https://community.secop.gov.co.evil.test/Public/1",
        "https://community.secop.gov.co:bad/Public/1",
    ]:
        assert source_link({"urlproceso": {"url": value}})[1] == "Conjunto de datos oficial"


async def test_adapter_live_shape_pagination_and_privacy(secop_metadata, secop_row):
    requests = []
    rows = [dict(secop_row, source_row_id=str(i), id_contrato=f"C{i}") for i in range(201)]

    def handler(request):
        requests.append(request)
        if request.url.path == META_PATH:
            return httpx.Response(200, json=secop_metadata)
        assert request.url.path == API_PATH
        assert "documento_proveedor in" in request.url.params["$where"]
        if "count(*)" in request.url.params["$select"]:
            return httpx.Response(200, json=[{"n": "201"}])
        assert "nombre_representante_legal" not in request.url.params["$select"]
        assert "n_mero_de_cuenta" not in request.url.params["$select"]
        offset = int(request.url.params["$offset"])
        assert request.url.params["$order"] == ":id ASC"
        return httpx.Response(200, json=rows[offset : offset + 200])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        records, updated = await SecopSource(SocrataClient(http)).fetch(NIT, DV, 5000)
    assert len(records) == 201 and updated and len(requests) == 5


@pytest.mark.parametrize(
    "failure", ["schema", "cap", "changed", "duplicate", "truncated", "invalid_count", "field_type"]
)
async def test_adapter_rejects_incomplete_results(secop_metadata, secop_row, failure):
    calls = 0

    def handler(request):
        nonlocal calls
        if request.url.path == META_PATH:
            calls += 1
            data = copy.deepcopy(secop_metadata)
            if failure == "schema":
                data["columns"] = [
                    c for c in data["columns"] if c["fieldName"] != "documento_proveedor"
                ]
            if failure == "changed" and calls > 1:
                data["rowsUpdatedAt"] += 1
            return httpx.Response(200, json=data)
        if "count(*)" in request.url.params["$select"]:
            return httpx.Response(
                200,
                json=[
                    {
                        "n": "bad"
                        if failure == "invalid_count"
                        else "6000"
                        if failure == "cap"
                        else "2"
                    }
                ],
            )
        rows = [secop_row, dict(secop_row, source_row_id="row-2")]
        if failure == "duplicate":
            rows[1] = secop_row
        if failure == "truncated":
            rows = []
        if failure == "field_type":
            rows[0] = dict(secop_row, valor_del_contrato={"bad": 1})
        return httpx.Response(200, json=rows)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(SourceError):
            await SecopSource(SocrataClient(http)).fetch(NIT, DV, 5000)


async def test_upstream_timeout_rate_limit_and_host_allowlist():
    for code in (429, 500, 403):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r, code=code: httpx.Response(code, headers={"Retry-After": "30"})
            )
        ) as http:
            source = SecopSource(SocrataClient(http, retries=1))
            with pytest.raises(SourceError):
                await source.metadata()
    http = AsyncMock()
    with pytest.raises(ValueError):
        await SocrataClient(http).get("https://evil.test/resource")
    http.stream.assert_not_called()


def test_secop_refresh_uses_existing_rate_controls():
    from starlette.requests import Request

    from app.core.config import Settings
    from app.core.rate_limits import RequestLimiter

    limiter = RequestLimiter(Settings(rate_limits_enabled=True), clock=lambda: 1.0)
    scope = dict(
        type="http",
        method="POST",
        path="/api/v1/companies/00000000-0000-0000-0000-000000000001/screening/secop/refresh",
        query_string=b"",
        headers=[],
        client=("127.0.0.1", 1234),
    )
    assert limiter.check(Request(scope)) == 0
    assert limiter.check(Request(dict(scope, client=("127.0.0.2", 1234)))) > 0


async def test_secop_api_validates_filters_origin_and_body_without_upstream():
    from app.main import app

    base = "/api/v1/companies/00000000-0000-0000-0000-000000000001/screening/secop"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        for query in (
            "page_size=51",
            "page=0",
            "sort=raw_sql",
            "year=1700",
            "status=unrecognized",
            "direction=random",
            "run_id=bad",
        ):
            assert (await client.get(base + "/contracts?" + query)).status_code == 422
        assert (await client.post(base + "/refresh", content=b"arbitrary query")).status_code == 413
        assert (
            await client.post(base + "/refresh", headers={"Origin": "https://evil.test"})
        ).status_code == 403


def test_cop_top_buyers_rank_by_value_not_count(secop_row):
    contract = verified_contracts([secop_row], NIT, DV, NOW)[0][0][0]
    expensive = contract.model_copy(
        update={
            "contract_id": "expensive",
            "buyer": "LARGE BUYER",
            "buyer_nit": "800000001",
            "value": Decimal("999.99"),
        }
    )
    cheap = contract.model_copy(update={"contract_id": "cheap", "value": Decimal("0.02")})
    result = aggregate([contract, cheap, expensive])
    assert result.top_buyers[0].label == "LARGE BUYER"
    assert result.total_values == {"COP": Decimal("1100.02")}
    assert result.annual[0].values == {"COP": Decimal("1100.02")}


def test_nine_and_ten_digit_rules_require_exact_base_and_confirmed_dv(secop_row):
    from app.integrations.secop.adapter import supplier_variants

    assert supplier_matches(dict(secop_row, documento_proveedor=NIT), NIT, None)
    assert supplier_matches(dict(secop_row, documento_proveedor=NIT + "0"), NIT, "0")
    assert NIT + "0" in supplier_variants(NIT, "0")
    assert NIT + DV not in supplier_variants(NIT, None)
    assert not supplier_matches(dict(secop_row, documento_proveedor="12345678"), "12345678", DV)
    assert not supplier_matches(dict(secop_row, documento_proveedor=NIT + DV), NIT + DV, None)
    rows = [
        secop_row,
        dict(
            secop_row, id_contrato="TEN-DIGITS", source_row_id="row-2", documento_proveedor=NIT + DV
        ),
    ]
    matches, excluded = verified_contracts(rows, NIT, DV, NOW)
    assert len(matches) == 2 and excluded == 0
    assert {c.normalized_supplier_identifier for c, _ in matches} == {NIT}
    assert matches[1][0].original_supplier_identifier == NIT + DV


def test_every_reported_status_is_its_own_group_even_for_single_contracts(secop_row):
    names = ["Aprobado", "En aprobación", "Enviado proveedor", "Estado nuevo"]
    rows = [
        dict(secop_row, id_contrato=f"CONTRACT-{i}", source_row_id=f"row-{i}", estado_contrato=name)
        for i, name in enumerate(names)
    ]
    contracts, _ = verified_contracts(rows, NIT, DV, NOW)
    result = aggregate([c for c, _ in contracts])
    assert {g.label: g.count for g in result.statuses} == {name: 1 for name in names}
    assert sum(g.count for g in result.statuses) == result.total_contracts
    assert all(g.label != "other" for g in result.statuses)
    assert (
        aggregate([contracts[0][0].model_copy(update={"raw_status": "  "})]).statuses[0].label
        == "No informado"
    )
