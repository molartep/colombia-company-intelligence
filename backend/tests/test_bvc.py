from unittest.mock import AsyncMock, patch

import httpx
import pytest
from capital_fixtures import SYNTHETIC_BVC_CODE, bvc_html

from app.core.errors import SourceError
from app.integrations.capital_markets.bvc import BvcPublicPages, parse_quote, validate_page


@pytest.mark.parametrize("paired", [False, True])
def test_public_bvc_fields_match_only_exact_source_code(paired):
    quote = parse_quote(bvc_html(paired=paired), SYNTHETIC_BVC_CODE)
    assert quote.ticker == "SYNTHETIC" and str(quote.last_price) == "1234.50"
    assert quote.isin == "CO0000000001" and quote.code != quote.isin
    assert quote.currency is None  # Do not infer a currency from a dollar sign or the URL.
    assert quote.state == "Activo"


def test_wrong_code_and_changed_layout_are_not_identity_matches():
    for content in [bvc_html(code="COSYNTH00002"), b"<html>SYNTHETIC shell</html>"]:
        with pytest.raises(ValueError):
            parse_quote(content, SYNTHETIC_BVC_CODE)
    quote = parse_quote(bvc_html(price="No disponible"), SYNTHETIC_BVC_CODE)
    assert quote.last_price is None and quote.ticker == "SYNTHETIC"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.test/renta-variable-mercado-local/synthetic",
        "https://www.bvc.com.co.evil.test/renta-variable-mercado-local/synthetic",
        "http://www.bvc.com.co/renta-variable-mercado-local/synthetic",
        "https://www.bvc.com.co/renta-variable-mercado-local/synthetic?url=http://127.0.0.1",
    ],
)
def test_bvc_urls_are_allowlisted(url):
    with pytest.raises(ValueError):
        validate_page(url)


async def test_bvc_success_uses_public_html_without_guessing_fields():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=bvc_html()))
    ) as http:
        adapter = BvcPublicPages(http)
        content = await adapter.fetch(
            "https://www.bvc.com.co/renta-variable-mercado-local/synthetic", SYNTHETIC_BVC_CODE
        )
        assert parse_quote(content, SYNTHETIC_BVC_CODE).ticker == "SYNTHETIC"


async def test_bvc_403_is_a_source_failure_without_browser_evasion_or_empty_result():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(403))
    ) as http:
        adapter = BvcPublicPages(http)
        with patch.object(adapter, "render", new_callable=AsyncMock) as render:
            with pytest.raises(SourceError) as error:
                await adapter.fetch(
                    "https://www.bvc.com.co/renta-variable-mercado-local/synthetic",
                    SYNTHETIC_BVC_CODE,
                )
            assert error.value.code == "bvc_http_403"
            render.assert_not_awaited()


def test_split_price_labels_and_conflicting_prices():
    content = bvc_html().replace("Último precio".encode(), "Último</h2><h2>precio".encode())
    assert str(parse_quote(content, SYNTHETIC_BVC_CODE).last_price) == "1234.50"
    conflict = bvc_html().replace(
        "<h2>Información".encode(),
        "<p>Último precio</p><span>999.00</span><h2>Información".encode(),
    )
    with pytest.raises(ValueError, match="Conflicting"):
        parse_quote(conflict, SYNTHETIC_BVC_CODE)


async def test_bvc_transport_timeout_is_not_an_empty_stock_record():
    def timeout(request):
        raise httpx.ReadTimeout("SYNTHETIC timeout")

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as http:
        with pytest.raises(SourceError) as error:
            await BvcPublicPages(http).fetch(
                "https://www.bvc.com.co/renta-variable-mercado-local/synthetic", SYNTHETIC_BVC_CODE
            )
        assert error.value.code == "bvc_transport_error"
