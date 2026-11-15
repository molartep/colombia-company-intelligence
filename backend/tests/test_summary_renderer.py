from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from capital_fixtures import issuer_details_html
from playwright.async_api import TimeoutError as BrowserTimeout

from app.core.errors import SourceError
from app.integrations.capital_markets.issuer_details import parse_issuer_details
from app.integrations.capital_markets.summary_renderer import (
    RnveSummaryRenderer,
    allowed_request,
    summary_url,
)


@pytest.mark.parametrize(
    "url,method,kind,allowed",
    [
        ("https://www.superfinanciera.gov.co/SIMEV2/main.js", "GET", "script", True),
        ("https://www.superfinanciera.gov.co/sfcservices/SIMEV2/data", "GET", "xhr", True),
        ("https://www.superfinanciera.gov.co/image.png", "GET", "image", False),
        ("https://www.superfinanciera.gov.co/", "POST", "xhr", False),
        ("https://www.superfinanciera.gov.co.evil.test/", "GET", "script", False),
        ("http://127.0.0.1/", "GET", "document", False),
    ],
)
def test_renderer_network_allowlist(url, method, kind, allowed):
    assert allowed_request(url, method, kind) is allowed


def test_renderer_url_uses_only_verified_source_codes():
    assert summary_url("001", "007").endswith("/1/7/0")
    with pytest.raises(ValueError):
        summary_url("001", "../7")


async def browser_fixture(monkeypatch):
    import asyncio

    page = AsyncMock()
    page.set_default_timeout = MagicMock()
    response = SimpleNamespace(status=200, finished=AsyncMock())
    info = SimpleNamespace(value=asyncio.get_running_loop().create_future())
    info.value.set_result(response)
    manager = MagicMock()
    manager.__aenter__ = AsyncMock(return_value=info)
    manager.__aexit__ = AsyncMock(return_value=False)
    page.expect_response = MagicMock(return_value=manager)
    page.goto.return_value = response
    page.content.return_value = issuer_details_html().decode()
    context = AsyncMock()
    context.new_page.return_value = page
    browser = AsyncMock()
    browser.new_context.return_value = context
    renderer = RnveSummaryRenderer(2)
    monkeypatch.setattr(renderer, "_get_browser", AsyncMock(return_value=browser))
    return renderer, context, page


async def test_renderer_normal_navigation_waits_for_source_and_closes_context(monkeypatch):
    renderer, context, page = await browser_fixture(monkeypatch)
    content = await renderer.fetch("001", "001", "SYNTHETIC EMISOR SAS")
    assert content == issuer_details_html()
    assert page.expect_response.call_count == 2
    page.goto.assert_awaited_once_with(summary_url("001", "001"), wait_until="domcontentloaded")
    context.close.assert_awaited_once()
    # No regulator service credential is extracted or passed to a separate HTTP client.
    assert not page.request.get.called


async def test_renderer_timeout_is_source_failure_and_closes_context(monkeypatch):
    renderer, context, page = await browser_fixture(monkeypatch)
    page.wait_for_function.side_effect = BrowserTimeout("SYNTHETIC timeout")
    with pytest.raises(SourceError, match="Could not retrieve"):
        await renderer.fetch("001", "001", "SYNTHETIC EMISOR SAS")
    context.close.assert_awaited_once()


async def test_renderer_rejected_page_is_not_empty_evidence(monkeypatch):
    renderer, context, page = await browser_fixture(monkeypatch)
    page.goto.return_value = SimpleNamespace(status=429)
    with pytest.raises(SourceError):
        await renderer.fetch("001", "001", "SYNTHETIC EMISOR SAS")
    context.close.assert_awaited_once()


def test_summary_extended_trading_name_still_requires_same_identity():
    from capital_fixtures import SYNTHETIC_NIT

    from app.integrations.capital_markets.parsers import verification_digit

    row = parse_issuer_details(
        issuer_details_html(
            **{"Nombre:": "SYNTHETIC EMISOR SAS podrá girar también con otro nombre"}
        ),
        issuer_name="SYNTHETIC EMISOR SAS",
        source_nit=SYNTHETIC_NIT + verification_digit(SYNTHETIC_NIT),
        entity_type="001",
        entity_code="001",
    )
    assert row.raw["Nombre:"].startswith("SYNTHETIC EMISOR SAS")
