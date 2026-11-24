"""Render synthetic RUES timeout/error states; no upstream requests or company data changes."""

import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "docs/design/fixtures/ui-review.json").read_text())
EN = json.loads((ROOT / "frontend/src/i18n/locales/en.json").read_text())
OUT = ROOT / "docs/design/assets/rues-timeout"


async def main(base_url):
    OUT.mkdir(exist_ok=True)
    report = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for language in ["en", "es"]:
            for width in [320, 390, 768, 1440]:
                for cached in [True, False]:
                    context = await browser.new_context(
                        viewport={"width": width, "height": 1000},
                        reduced_motion="reduce",
                    )
                    await context.add_init_script(
                        f"localStorage.setItem('cci.language', '{language}')"
                    )
                    page = await context.new_page()

                    async def route(r, _request, cached=cached):
                        if cached:
                            return await r.fulfill(
                                json={
                                    "items": [
                                        dict(
                                            DATA["company"],
                                            registration_number="00123",
                                            chamber="SYNTHETIC",
                                            chamber_code="99",
                                            registration_date="20200115",
                                            renewal_date="20260120",
                                            match_type="exact_legal_name",
                                            evidence=[],
                                            data_source="rues",
                                        )
                                    ],
                                    "page": 1,
                                    "page_size": 20,
                                    "has_more": False,
                                    "stale": True,
                                    "warning": EN["messages"]["rues"][
                                        "timeoutFallback"
                                    ],
                                    "ranking_scope": "current cached page",
                                }
                            )
                        await r.fulfill(
                            status=503,
                            json={
                                "error": {
                                    "code": "source_timeout",
                                    "message": "RUES lookup exceeded its configured time limit.",
                                }
                            },
                        )

                    await page.route("**/api/v1/companies?**", route)
                    await page.goto(base_url + "/?q=Thomas+greg")
                    notice = page.locator(
                        ".refresh-alert" if cached else ".notice.danger"
                    )
                    await notice.wait_for()
                    text = await notice.inner_text()
                    assert "RUES" in text and "datos.gov.co" in text
                    assert "source_timeout" not in text
                    assert not await page.evaluate(
                        "document.documentElement.scrollWidth > innerWidth"
                    )
                    if (language, width) in [("en", 1440), ("es", 390)]:
                        await page.screenshot(
                            path=str(
                                OUT
                                / f"{'cached' if cached else 'no-cache'}-{language}-{width}.png"
                            ),
                            full_page=True,
                        )
                    report.append(
                        {
                            "language": language,
                            "width": width,
                            "cached": cached,
                            "rues_attributed": True,
                            "raw_code_hidden": True,
                            "page_overflow": False,
                        }
                    )
                    await context.close()
        (OUT / "inspection.json").write_text(json.dumps(report, indent=2) + "\n")
        await browser.close()


parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://127.0.0.1:5174")
asyncio.run(main(parser.parse_args().base_url.rstrip("/")))
