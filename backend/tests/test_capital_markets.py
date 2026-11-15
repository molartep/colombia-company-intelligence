from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from capital_fixtures import SYNTHETIC_NIT, issuer_xlsx, security_html

from app.core.errors import SourceError
from app.integrations.capital_markets.parsers import (
    amount,
    calendar_date,
    category,
    issuer_nit,
    parse_issuers,
    parse_securities,
    verification_digit,
)
from app.integrations.capital_markets.reports import (
    BvcUnavailable,
    OfficialReports,
    securities_url,
    store_artifact,
)
from app.integrations.capital_markets.service import summary
from app.integrations.capital_markets.types import RegistrationStatus, SecurityCategory


def test_issuer_schema_source_codes_nit_rule_and_private_fields():
    rows, stamp = parse_issuers(issuer_xlsx(), "concatenated-dv")
    row = rows[0]
    assert stamp and row.external_id == "001:001"
    assert row.nit == SYNTHETIC_NIT and row.identity_eligible
    assert row.verification_digit == verification_digit(SYNTHETIC_NIT)
    assert row.raw["Direccion"] == "SYNTHETIC BUSINESS ADDRESS"
    assert row.raw["Correo electronico"] == "registry@example.test"
    assert "Nivel de supervisión" not in row.raw
    preserved, _ = parse_issuers(issuer_xlsx())
    assert preserved[0].nit != row.nit and not preserved[0].identity_eligible


def test_missing_nit_foreign_and_compartment_identifiers_are_not_truncated():
    for value, kind in [
        ("", "001"),
        ("9001234567001", "095"),
        ("9001234567001", "092"),
        ("4444005240", "141"),
    ]:
        nit, dv, eligible = issuer_nit(value, kind, "concatenated-dv")
        assert not eligible
        assert nit == (value or None)
    assert not issuer_nit("1234567899", "001", "concatenated-dv")[2]
    assert (
        issuer_nit(SYNTHETIC_NIT + "-" + verification_digit(SYNTHETIC_NIT), "001", "preserve")[0]
        == SYNTHETIC_NIT
    )


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"not a workbook",
        b"PKnotazip",
        issuer_xlsx([("SYNTHETIC", "12345", "BAD", "001")]),
        issuer_xlsx([("SYNTHETIC", "12345", "001", "001"), ("SYNTHETIC", "12345", "001", "001")]),
    ],
)
def test_invalid_spreadsheets_and_duplicate_issuer_keys_fail(content):
    with pytest.raises(ValueError):
        parse_issuers(content)


def test_formula_rejected_without_execution():
    with pytest.raises(ValueError, match="formulas"):
        parse_issuers(issuer_xlsx([('=HYPERLINK("https://invalid.test")', "123456", "001", "001")]))


def test_multiple_instruments_preserve_ann_and_do_not_invent_symbols():
    rows, observed = parse_securities(security_html(), "SYNTHETIC EMISOR SAS")
    assert observed and len(rows) == 2
    assert rows[0].security_category == SecurityCategory.BONDS
    assert rows[1].security_category == SecurityCategory.DEBT
    assert rows[0].ann_code == "SYNTHETIC-ANN"
    assert rows[0].authorized_amount == amount("1000000,50")
    assert rows[0].rnve_registration_date == "2024-02-29"
    assert rows[1].bvc_registration_date is None
    assert "ticker" not in type(rows[0]).model_fields
    with pytest.raises(ValueError, match="different issuer"):
        parse_securities(
            security_html(issuer="SYNTHETIC EMISOR SAS SUBSIDIARY"), "SYNTHETIC EMISOR SAS"
        )


@pytest.mark.parametrize(
    "prefix,expected",
    [
        ("AO", SecurityCategory.COMMON),
        ("ADP", SecurityCategory.PREFERRED),
        ("AP", SecurityCategory.EQUITY),
        ("BOCEAS", SecurityCategory.BONDS),
        ("ACE", SecurityCategory.DEBT),
        ("PC", SecurityCategory.PAPER),
        ("TP", SecurityCategory.OTHER),
        ("UNKNOWN", SecurityCategory.OTHER),
    ],
)
def test_classification_uses_verified_conventions(prefix, expected):
    assert category(prefix + " SYNTHETIC") == expected


@pytest.mark.parametrize("value", ["N/A", "00000000", "29/02/2023", "01/01/1900", "31/12/9999"])
def test_invalid_dates_remain_missing(value):
    assert calendar_date(value) is None


def test_amount_currency_and_security_schema_changes():
    assert str(amount("200.000.000.000")) == "200000000000"
    assert amount("not an amount") is None
    assert calendar_date("29/02/2024") == "2024-02-29"
    with pytest.raises(ValueError):
        parse_securities(security_html().replace(b"ANN", b"CHANGED", 1), "SYNTHETIC EMISOR SAS")
    with pytest.raises(ValueError):
        parse_securities(
            security_html().replace(b"encontrados 2", b"encontrados 200"), "SYNTHETIC EMISOR SAS"
        )
    with pytest.raises(ValueError):
        parse_securities(b"<html>Login</html>", "SYNTHETIC EMISOR SAS")


async def test_public_report_client_fixed_host_retry_timeout_and_bvc_unavailable():
    seen = []

    def handler(request):
        seen.append(request)
        return (
            httpx.Response(429, headers={"Retry-After": "0"})
            if len(seen) == 1
            else httpx.Response(200, content=security_html())
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with patch(
            "app.integrations.capital_markets.reports.asyncio.sleep", new_callable=AsyncMock
        ):
            assert await OfficialReports(http).securities("001", "023")
    assert len(seen) == 2 and seen[0].url.params["entidad"] == "023"
    assert seen[0].url.host == "www.superfinanciera.gov.co"
    assert seen[0].url.params["tipoEntidad"] == "001"
    for code in ["../001", "https://invalid", "001&x=1"]:
        with pytest.raises(ValueError):
            securities_url("001", code)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(429, headers={"Retry-After": "120"}))
    ) as http:
        with pytest.raises(SourceError):
            await OfficialReports(http).securities("001", "001")

    def timeout(request):
        raise httpx.ReadTimeout("synthetic")

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as http:
        with pytest.raises(SourceError):
            await OfficialReports(http, retries=0).securities("001", "001")
    with pytest.raises(SourceError):
        await BvcUnavailable().verify_listing("SYNTHETIC")


def test_content_addressed_storage_is_idempotent(tmp_path: Path):
    digest = store_artifact(b"synthetic report", tmp_path)
    assert store_artifact(b"synthetic report", tmp_path) == digest
    assert len(list(tmp_path.iterdir())) == 1
    (tmp_path / digest).write_bytes(b"tampered")
    with pytest.raises(ValueError):
        store_artifact(b"synthetic report", tmp_path)


def test_summaries_do_not_imply_listed_equity_or_never_registered():
    value = summary(RegistrationStatus.ACTIVE, False, True, False)
    assert "deuda" in value and "No se ha verificado" in value
    assert "Esto no descarta registros históricos" in summary(
        RegistrationStatus.NOT_FOUND, False, False, False
    )
    assert "posible coincidencia" in summary(RegistrationStatus.UNKNOWN, True, False, False)
    assert "última actualización falló" not in summary(RegistrationStatus.ACTIVE, False, True, True)


def test_issuer_details_allowlist_and_missing_fields():
    from capital_fixtures import issuer_details_html

    from app.integrations.capital_markets.issuer_details import parse_issuer_details

    row = parse_issuer_details(
        issuer_details_html(),
        issuer_name="SYNTHETIC EMISOR SAS",
        source_nit=SYNTHETIC_NIT + verification_digit(SYNTHETIC_NIT),
        entity_type="001",
        entity_code="001",
    )
    assert row.raw["Correo institucional"] == "registry@example.test"
    assert row.raw["Nro. Miembros Junta Directiva"] == "7"
    assert row.raw["Redes Sociales"] == "" and row.social_urls == []
    assert "Documento representante" not in row.raw
    assert "super@example.test" not in str(row.raw)


@pytest.mark.parametrize(
    "field,value",
    [
        ("Nombre:", "OTHER SYNTHETIC COMPANY"),
        ("Tipo Entidad:", "066 - OTHER"),
        ("Código Entidad:", "002"),
        ("NIT:", "900999999-1"),
    ],
)
def test_issuer_details_reject_other_identities(field, value):
    from capital_fixtures import issuer_details_html

    from app.integrations.capital_markets.issuer_details import parse_issuer_details

    with pytest.raises(ValueError):
        parse_issuer_details(
            issuer_details_html(**{field: value}),
            issuer_name="SYNTHETIC EMISOR SAS",
            source_nit=SYNTHETIC_NIT + verification_digit(SYNTHETIC_NIT),
            entity_type="001",
            entity_code="001",
        )


@pytest.mark.parametrize(
    "url",
    [
        "https://example.test/SIMEV2/rnve/resumenentidad/1/1/0",
        "https://www.superfinanciera.gov.co/SIMEV2/rnve/resumenentidad/66/1/0",
        "https://user@www.superfinanciera.gov.co/SIMEV2/rnve/resumenentidad/1/1/0",
    ],
)
def test_issuer_details_reject_wrong_source_url(url):
    from app.integrations.capital_markets.issuer_details import validate_details_url

    with pytest.raises(ValueError):
        validate_details_url(url, "001", "001")


def test_issuer_details_social_links_only_from_social_row():
    from capital_fixtures import issuer_details_html

    from app.integrations.capital_markets.issuer_details import parse_issuer_details

    content = (
        issuer_details_html().replace(
            b"<td>Redes Sociales</td><td></td>",
            b'<td>Redes Sociales</td><td><a href="https://www.example.test/social">Social</a></td>',
        )
        + b'<footer><a href="https://www.example.test/regulator">Regulator</a></footer>'
    )
    row = parse_issuer_details(
        content,
        issuer_name="SYNTHETIC EMISOR SAS",
        source_nit=SYNTHETIC_NIT + verification_digit(SYNTHETIC_NIT),
        entity_type="001",
        entity_code="001",
    )
    assert row.social_urls == ["https://www.example.test/social"]


async def test_sfc_transport_does_not_receive_socrata_token(monkeypatch):
    from fastapi import FastAPI

    from app.core.config import get_settings
    from app.main import lifespan

    monkeypatch.setattr(get_settings(), "socrata_app_token", "SYNTHETIC-SOCRATA-TOKEN")
    isolated_app = FastAPI()
    async with lifespan(isolated_app):
        client = isolated_app.state.rnve_securities.client
        assert "X-App-Token" not in client.headers
        assert client.timeout.read == get_settings().capital_markets_timeout


async def test_rues_manual_refresh_queries_one_exact_source_row(record):
    from types import SimpleNamespace

    from app.integrations.rues.adapter import RuesDataSource

    client = SimpleNamespace(records=AsyncMock(return_value=[record]))
    rows = await RuesDataSource(client).record_by_id(record["upstream_id"])
    assert rows == [record]
    params = client.records.await_args.args[0]
    assert params["$limit"] == "1" and params["$offset"] == "0"
    assert params["$where"] == ":id = 'row-synthetic-001'"
