"""Download the observed official XLSX through SFC's public export controls."""

import asyncio
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import Error, Route, async_playwright

from app.core.errors import SourceError
from app.integrations.capital_markets.parsers import MAX_BYTES
from app.integrations.capital_markets.types import DIRECTORY_URL


def read_download(path: str) -> bytes:
    with Path(path).open("rb") as stream:
        return stream.read(MAX_BYTES + 1)


async def download_directory() -> bytes:
    # No caller-provided URLs, browser credentials, internal API calls or shared cookies.
    try:
        async with asyncio.timeout(90), async_playwright() as driver:
            browser = await driver.chromium.launch(channel="chromium", headless=True)
            try:
                context = await browser.new_context(accept_downloads=True, service_workers="block")

                async def restrict(route: Route) -> None:
                    url = urlparse(route.request.url)
                    if (
                        url.scheme == "https"
                        and url.netloc == "www.superfinanciera.gov.co"
                        and route.request.method == "GET"
                        and route.request.resource_type not in {"image", "font", "media"}
                    ):
                        await route.continue_()
                    else:
                        await route.abort()

                await context.route("**/*", restrict)
                page = await context.new_page()
                page.set_default_timeout(30000)
                response = await page.goto(DIRECTORY_URL, wait_until="domcontentloaded")
                if not response or response.status != 200:
                    raise SourceError(
                        "rnve_download_failed", "SFC's issuer directory is unavailable."
                    )
                await page.get_by_role(
                    "button", name=re.compile(r"^\s*DESCARGAR EMISORES\s*$")
                ).click()
                async with page.expect_download() as pending:
                    await page.get_by_text("REPORTE EXCEL", exact=True).filter(visible=True).click()
                download = await pending.value
                path = await download.path()
                if not path or not download.suggested_filename.lower().endswith(".xlsx"):
                    raise SourceError("rnve_download_failed", "SFC did not return an XLSX export.")
                # Read a bounded file, never the publisher's suggested filesystem name.
                content = await asyncio.to_thread(read_download, str(path))
                if len(content) > MAX_BYTES:
                    raise SourceError(
                        "rnve_download_failed", "SFC export exceeds the 10 MiB limit."
                    )
                return content
            finally:
                await browser.close()
    except (TimeoutError, Error, OSError) as exc:
        raise SourceError(
            "rnve_download_failed",
            "Could not download the official RNVE export. Use the official page's "
            "DESCARGAR EMISORES → REPORTE EXCEL control and import that file instead.",
        ) from exc
