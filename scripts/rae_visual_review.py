"""Synthetic UI QA. Requires Vite on localhost:5174; never queries official sources."""

import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
D = json.loads((ROOT / "docs/design/fixtures/ui-review.json").read_text())
DEMO = json.loads((ROOT / "docs/design/fixtures/rae-demo.json").read_text())
OUT = ROOT / "docs/design/assets/rainbird"
OUT.mkdir(exist_ok=True)


async def main():
    report = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for lang in ["en", "es"]:
            for width in [390, 768, 1440]:
                context = await browser.new_context(
                    viewport={"width": width, "height": 1000}, reduced_motion="reduce"
                )
                await context.add_init_script(
                    f"localStorage.setItem('cci.language','{lang}')"
                )
                page = await context.new_page()
                errors = []
                page.on(
                    "pageerror",
                    lambda error, captured=errors: captured.append(str(error)),
                )

                async def route(r):
                    path = urlparse(r.request.url).path
                    if path.endswith(("/involvement", "/demo")):
                        body = DEMO
                    elif path.endswith("/secop"):
                        body = D["secop"]
                    elif path.endswith("/contracts"):
                        body = {
                            "items": D["contracts"][:5],
                            "total": 7,
                            "page": 1,
                            "page_size": 5,
                            "has_more": True,
                            "run_id": D["id"],
                        }
                    elif path.endswith("/sources"):
                        body = D["records"]
                    elif path.endswith("/" + D["id"]):
                        body = D["company"]
                    elif path.endswith("/parameters"):
                        body = D["catalog"]
                    else:
                        return await r.fulfill(
                            status=404,
                            json={
                                "error": {
                                    "code": "synthetic_missing",
                                    "message": "Synthetic",
                                }
                            },
                        )
                    await r.fulfill(json=body)

                await page.route("**/api/v1/**", route)
                await page.goto(
                    "http://127.0.0.1:5174/companies/" + D["id"] + "?tab=screening"
                )
                card = page.locator(".involvement-card")
                await card.wait_for()
                await card.locator(".involvement-dimension").first.wait_for()
                await card.scroll_into_view_if_needed()
                await page.screenshot(
                    path=str(OUT / f"card-{lang}-{width}.png"), full_page=True
                )
                trigger = card.locator("button.text-link")
                await trigger.click()
                dialog = page.locator("dialog[open]")
                await dialog.wait_for()
                assert (
                    await dialog.get_attribute("aria-labelledby") == "rae-dialog-title"
                )
                assert (
                    await dialog.locator('a[target="_blank"]').first.get_attribute(
                        "rel"
                    )
                    == "noopener noreferrer"
                )
                await page.screenshot(path=str(OUT / f"dialog-{lang}-{width}.png"))
                await page.keyboard.press("Escape")
                assert await trigger.evaluate("(e)=>e===document.activeElement")
                await card.locator(".involvement-dimension").nth(2).click()
                await dialog.locator(
                    ".involvement-decision-detail[open] .involvement-node-rule > details > summary"
                ).first.click()
                await dialog.locator(
                    ".involvement-decision-detail[open]"
                ).scroll_into_view_if_needed()
                await page.screenshot(path=str(OUT / f"evidence-{lang}-{width}.png"))
                await page.keyboard.press("Escape")
                await page.goto(
                    "http://127.0.0.1:5174/methodology/rae?demo=true&decision=recent_participation"
                )
                await page.locator(".involvement-decision-detail").first.wait_for()
                await page.screenshot(
                    path=str(OUT / f"methodology-{lang}-{width}.png"), full_page=True
                )
                overflow = await page.evaluate(
                    "document.documentElement.scrollWidth>innerWidth"
                )
                assert not overflow and not errors, (width, errors)
                report.append(
                    {
                        "language": lang,
                        "width": width,
                        "overflow": overflow,
                        "browser_errors": errors,
                        "escape_focus_return": True,
                    }
                )
                await context.close()
        await browser.close()
    (OUT / "inspection.json").write_text(json.dumps(report, indent=2) + "\n")


asyncio.run(main())
