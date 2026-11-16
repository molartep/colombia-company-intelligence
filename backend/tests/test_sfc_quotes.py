"""Synthetic fixtures for the verified official SFC quote layout."""

from decimal import Decimal

import httpx
import pytest

from app.core.errors import SourceError
from app.integrations.capital_markets.secondary_quotes import exact_match, parse_la_republica
from app.integrations.capital_markets.sfc_quotes import SfcQuotePages, parse_daily_quote, quote_url

CODE = "COSYNTH00001"


def sfc_fixture(code=CODE, price="1,234.56", action_class="ORDINARIA"):
    return f"""<table><tr><td>AO SYNTHETIC S.A.</td><td>Fecha de reporte : 12/11/2026</td></tr>
    <tr><td>CLASE DE ACCIÓN</td><td>{action_class}</td></tr>
    <tr><td>CODIGO DE LA ACCIÓN</td><td>{code}</td></tr></table>
    <table><tr><td>PROMEDIO PONDERADO</td><td>MAX</td><td>MIN</td><td>Vr. PATRIMONIAL</td></tr>
    <tr><td>12/11/2026</td><td>01/11/2026</td><td>02/11/2026</td><td></td></tr>
    <tr><td>{price}</td><td>2,000.00</td><td>1,000.00</td><td>1.00</td></tr></table>""".encode()


def test_sfc_price_is_weighted_not_last_trade_and_identity_requires_actual_ann():
    quote = parse_daily_quote(sfc_fixture(action_class="PRIVILEGIADA"))
    assert quote.last_price == Decimal("1234.56") and quote.currency == "COP"
    assert quote.price_kind == "daily_weighted_average"
    assert quote.price_date.isoformat() == "2026-11-12" and quote.price_as_of is None
    assert quote.ticker is None and quote.source_note
    assert exact_match(quote, None, [], {CODE}) == ("exact_ann", CODE, CODE)
    assert exact_match(quote, None, ["SYNTHETIC S.A."], {"COOTHER00001"}) is None


@pytest.mark.parametrize(
    "payload",
    [
        sfc_fixture(price="NaN"),
        sfc_fixture().replace(b"12/11/2026", b"31/02/2026"),
        sfc_fixture(code="MISSING"),
        sfc_fixture().replace(b"PROMEDIO PONDERADO", b"UNKNOWN"),
    ],
)
def test_sfc_missing_changed_or_malformed_fields_do_not_produce_prices(payload):
    with pytest.raises((ValueError, SourceError)):
        parse_daily_quote(payload)


def test_quote_without_technical_sheet_is_not_a_verified_ticker_match():
    with pytest.raises(SourceError) as error:
        parse_la_republica(b"<p>Descripci\xc3\xb3n</p><p>Accion SYNTHETIC</p><p>$ 1.234</p>")
    assert error.value.code == "quote_identity_missing"


async def test_sfc_transport_rate_limit_and_fixed_ann_routing():
    calls = []

    def handler(request):
        calls.append(request)
        return (
            httpx.Response(429, headers={"Retry-After": "0"})
            if len(calls) == 1
            else httpx.Response(200, content=sfc_fixture())
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        source = SfcQuotePages(http)
        assert await source.fetch(quote_url(CODE)) == sfc_fixture()
        with pytest.raises(ValueError):
            await source.fetch("https://example.com/quote")
    assert len(calls) == 2 and all(r.url.host == "www.superfinanciera.gov.co" for r in calls)
    assert quote_url("../other") is None


async def test_sfc_transport_does_not_retry_404():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(SourceError):
            await SfcQuotePages(http).fetch(quote_url(CODE))
    assert len(calls) == 1
