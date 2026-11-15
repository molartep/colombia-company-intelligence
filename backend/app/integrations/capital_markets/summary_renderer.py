"""Render the ordinary public RNVE summary; never copy the SPA's API credentials."""

import asyncio
import re
from typing import Protocol
from urllib.parse import urlparse

from playwright.async_api import Browser, Error, Playwright, Route, async_playwright

from app.core.errors import SourceError
from app.integrations.capital_markets.parsers import MAX_BYTES


class SummaryRetriever(Protocol):
    async def fetch(self, entity_type: str, entity_code: str, issuer_name: str) -> bytes: ...


def summary_url(entity_type: str, entity_code: str) -> str:
    if not all(re.fullmatch(r"[0-9]{3}", value) for value in (entity_type, entity_code)):
        raise ValueError("Expected verified regulatory entity codes.")
    return (
        "https://www.superfinanciera.gov.co/SIMEV2/rnve/resumenentidad/"
        f"{int(entity_type)}/{int(entity_code)}/0"
    )


def allowed_request(url: str, method: str, resource_type: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.netloc == "www.superfinanciera.gov.co"
        and method == "GET"
        and resource_type not in {"image", "font", "media"}
    )


class RnveSummaryRenderer:
    """One lazy browser, isolated contexts, two concurrent pages and a total deadline."""

    def __init__(self, timeout: float = 30):
        self.timeout = timeout
        self._slots = asyncio.Semaphore(2)
        self._launch_lock = asyncio.Lock()
        self._driver: Playwright | None = None
        self._browser: Browser | None = None

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._driver:
            await self._driver.stop()
            self._driver = None

    async def _get_browser(self) -> Browser:
        async with self._launch_lock:
            if not self._browser or not self._browser.is_connected():
                if not self._driver:
                    self._driver = await async_playwright().start()
                self._browser = await self._driver.chromium.launch(
                    channel="chromium", headless=True
                )
            return self._browser

    async def fetch(self, entity_type: str, entity_code: str, issuer_name: str) -> bytes:
        url = summary_url(entity_type, entity_code)
        try:
            async with asyncio.timeout(self.timeout), self._slots:
                browser = await self._get_browser()
                context = await browser.new_context(service_workers="block", accept_downloads=False)
                try:

                    async def restrict(route: Route) -> None:
                        request = route.request
                        if allowed_request(request.url, request.method, request.resource_type):
                            await route.continue_()
                        else:
                            await route.abort()

                    await context.route("**/*", restrict)
                    page = await context.new_page()
                    page.set_default_timeout(self.timeout * 1000)
                    prefix = (
                        "https://www.superfinanciera.gov.co/sfcservices/SIMEV2/informacion-basica/"
                    )
                    suffix = f"tipo-entidad/{int(entity_type)}/codigo-entidad/{int(entity_code)}"
                    async with (
                        page.expect_response(prefix + suffix) as basic,
                        page.expect_response(prefix + "rnve/" + suffix) as administration,
                    ):
                        response = await page.goto(url, wait_until="domcontentloaded")
                        if not response or response.status != 200:
                            raise SourceError(
                                "rnve_summary_unavailable", "RNVE summary unavailable."
                            )
                    for expected in (basic, administration):
                        result = await expected.value
                        if result.status != 200:
                            raise SourceError(
                                "rnve_summary_unavailable", "RNVE summary could not be retrieved."
                            )
                        await result.finished()
                    await page.wait_for_function(
                        """() => {
                          const rows = [...document.querySelectorAll('table tr')]
                            .map(r => [...r.querySelectorAll('td')].map(c => c.innerText.trim()));
                          return rows.some(r => r[0] === 'Nombre:' && r[1])
                            && rows.some(r => r[0] === 'Nro. Miembros Junta Directiva');
                        }""",
                    )
                    # Allow Angular's response handlers to paint the final values, including blanks.
                    await page.evaluate(
                        "() => new Promise(r => requestAnimationFrame("
                        "() => requestAnimationFrame(r)))"
                    )
                    content = (await page.content()).encode()
                    if len(content) > MAX_BYTES:
                        raise SourceError(
                            "rnve_summary_oversized", "RNVE summary exceeds size limits."
                        )
                    return content
                finally:
                    await context.close()
        except (TimeoutError, Error) as exc:
            raise SourceError(
                "rnve_summary_unavailable", "Could not retrieve the public RNVE summary."
            ) from exc
