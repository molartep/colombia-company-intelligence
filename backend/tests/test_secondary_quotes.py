import asyncio
import os
from datetime import timedelta
from decimal import Decimal

import pytest

from app.integrations.capital_markets.secondary_quotes import (
    SecondaryQuote,
    colombian_number,
    exact_match,
    parse_la_republica,
    validate_lr_url,
)


def lr_fixture(name="COMPAÑÍA SINTÉTICA ANDINA S.A.S.", ticker="SYNTHETIC"):
    from html import escape

    parts = [
        "Descripción",
        "Acción de SYNTHETIC",
        "$ 1.234",
        "+$ 10",
        "+0,82%",
        "FECHA:",
        "13/11/2026 - 03:42:12 PM",
        "CANTIDAD",
        "10.000,000",
        "VOLUMEN",
        "$ 12.340.000,00",
        "Fuente:",
        "BVC",
        "ÚLTIMAS NOTICIAS SOBRE:",
        "SYNTHETIC unrelated price $ 9.999",
        "FICHA TÉCNICA:",
        name,
        "Cotiza sus acciones en la BVC:",
        "SÍ",
        "Nemotécnico:",
        ticker,
    ]
    return "".join(f"<div>{escape(part)}</div>" for part in parts).encode()


def quote(**overrides):
    return SecondaryQuote(
        legal_name=overrides.pop("legal_name", "SYNTHETIC SAS"),
        ticker="SYNTHETIC",
        last_price=Decimal("1234"),
        raw_price="$ 1.234",
        **overrides,
    )


def test_live_layout_scopes_price_technical_name_ticker_and_time():
    result = parse_la_republica(lr_fixture())
    assert result.last_price == Decimal("1234") and result.ticker == "SYNTHETIC"
    assert result.legal_name == "COMPAÑÍA SINTÉTICA ANDINA S.A.S."
    assert result.variation_percent == Decimal("0.82") and result.volume == Decimal("12340000.00")
    assert result.price_as_of.utcoffset() == timedelta(hours=-5)
    assert result.nit is None and result.ann_code is None


@pytest.mark.skipif(os.getenv("RUN_BROWSER_TESTS") != "1", reason="Opt-in Chromium contract test")
async def test_server_rendered_quote_with_hidden_body(monkeypatch):
    from playwright.async_api import BrowserContext, Route

    from app.integrations.capital_markets.secondary_quotes import LaRepublicaPublicPages

    original = BrowserContext.new_page

    async def fixture_page(context):
        page = await original(context)

        async def respond(route: Route):
            await route.fulfill(
                status=200,
                content_type="text/html; charset=utf-8",
                body=(
                    b"<html><head><style>body { display: none }</style></head><body>"
                    + lr_fixture()
                    + b"</body></html>"
                ),
            )

        await page.route("**/*", respond)
        return page

    monkeypatch.setattr(BrowserContext, "new_page", fixture_page)
    async with asyncio.timeout(10):
        content = await LaRepublicaPublicPages().fetch(
            "https://www.larepublica.co/indicadores-economicos/movimiento-accionario/synthetic"
        )
    parsed = parse_la_republica(content)
    assert parsed.legal_name == "COMPAÑÍA SINTÉTICA ANDINA S.A.S."
    assert parsed.last_price == Decimal("1234")


def test_exact_match_priority_and_conflicting_strong_identifiers():
    codes = {"COSYNTH00001"}
    assert exact_match(quote(nit="000123456"), "000123456", [], codes)[0] == "exact_nit"
    assert exact_match(quote(ann_code="COSYNTH00001"), "000123456", [], codes)[0] == "exact_ann"
    assert exact_match(quote(), "000123456", ["synthetic   sas"], codes)[0] == "exact_legal_name"
    assert (
        exact_match(
            quote(nit="999999999", ann_code="COSYNTH00001"), "000123456", ["SYNTHETIC SAS"], codes
        )
        is None
    )
    assert (
        exact_match(quote(ann_code="COSYNTH00002"), "000123456", ["SYNTHETIC SAS"], codes) is None
    )


def test_no_suffix_removal_fuzzy_name_ticker_only_or_ambiguous_instrument_matching():
    codes = {"COSYNTH00001"}
    assert exact_match(quote(), None, ["SYNTHETIC S.A.S."], codes) is None
    assert exact_match(quote(), None, ["SYNTHETIC OTHER SAS"], codes) is None
    assert exact_match(quote(), None, ["SYNTHETIC SAS"], codes | {"COSYNTH00002"}) is None
    assert exact_match(quote(share_class="preferred"), None, ["SYNTHETIC SAS"], codes) is None


@pytest.mark.parametrize(
    "url",
    [
        "https://example.test/indicadores-economicos/movimiento-accionario/synthetic",
        "https://www.larepublica.co/indicadores-economicos/movimiento-accionario/synthetic?url=http://localhost",
    ],
)
def test_secondary_host_and_route_are_fixed(url):
    with pytest.raises(ValueError):
        validate_lr_url(url)


def test_number_formats_and_changed_layout_are_not_silent_zero_quotes():
    assert colombian_number("$ 2.545") == Decimal("2545")
    assert colombian_number("$ 35.191.029.000,00") == Decimal("35191029000")
    with pytest.raises(ValueError):
        parse_la_republica(b"<html>SYNTHETIC blocked page</html>")


def test_former_names_are_explicit_and_retain_legal_suffixes():
    from app.integrations.capital_markets.equity_identity import former_legal_names

    title = "AO SINTÉTICA S.A. - ANTES SINTÉTICA S.A. E.S.P."
    names = former_legal_names(title)
    assert names == ["SINTÉTICA S.A. E.S.P."]
    assert exact_match(quote(legal_name=names[0]), None, names, {"COSYNTH00001"})
    assert not exact_match(quote(legal_name="SINTÉTICA SA ESP"), None, names, {"COSYNTH00001"})
    assert former_legal_names("BO SINTÉTICA - ANTES OTRA S.A.") == []
    assert former_legal_names("AO SINTÉTICA ANTES OTRA S.A.") == []


def lr_index_fixture(slug="synthetic", label="COMPAÑÍA SINTÉTICA ANDINA S.A.S."):
    from html import escape

    return (
        f'<a href="/indicadores-economicos/movimiento-accionario/{escape(slug)}">'
        f"{escape(label)}</a>"
    ).encode()
