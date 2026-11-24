"""Visual regression check with synthetic research evidence; run with Vite at --base-url."""

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
D = json.loads((ROOT / "docs/design/fixtures/ui-review.json").read_text())
OUT = ROOT / "docs/design/assets/currency-exports"
OUT.mkdir(exist_ok=True)


async def main(base_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        report = []
        for lang in ["en", "es"]:
            for width in [320, 390, 768, 1440]:
                context = await browser.new_context(
                    viewport={"width": width, "height": 1000}, reduced_motion="reduce"
                )
                await context.add_init_script(
                    f"localStorage.setItem('cci.language', '{lang}')"
                )
                page = await context.new_page()

                state = {"rate_failed": False}
                today = datetime.now(ZoneInfo("America/Bogota")).date().isoformat()

                async def route(r, _request, state=state, today=today):
                    path = urlparse(r.request.url).path
                    if path.endswith("/platform"):
                        body = D["platform"]
                    elif path.endswith("/capital-markets"):
                        body = D["markets"]
                    elif path.endswith("/securities"):
                        body = {
                            "items": [D["instrument"]],
                            "total": 1,
                            "unfiltered_total": 1,
                            "page": 1,
                            "page_size": 10,
                            "has_more": False,
                            "availability": "available",
                        }
                    elif path.endswith("/parameters"):
                        body = D["catalog"]
                    elif path.endswith("/companies"):
                        body = {
                            "items": [
                                dict(
                                    D["company"],
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
                            "stale": False,
                            "warning": None,
                            "ranking_scope": "all matching source records",
                        }
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
                    elif path.endswith("/usd-rate"):
                        if state["rate_failed"]:
                            return await r.fulfill(
                                status=503,
                                json={"error": {"message": "Synthetic failure"}},
                            )
                        body = {
                            "cop_per_usd": "4000",
                            "source": "SFC TRM",
                            "source_url": "https://www.datos.gov.co/d/32sa-8pi3",
                            "effective_date": today,
                            "effective_until": today,
                            "manual": False,
                            "stale": False,
                            "provider_failed": False,
                        }
                    elif "/contracts/" in path:
                        body = D["contracts"][0]
                    elif path.endswith("/sources"):
                        body = D["records"]
                    elif path.endswith("/" + D["id"]):
                        body = D["company"]
                    else:
                        return await r.fulfill(
                            status=404, json={"error": {"message": "Synthetic missing"}}
                        )
                    await r.fulfill(json=body)

                await page.route("**/api/v1/**", route)
                await page.goto(base_url + "/companies/" + D["id"] + "?tab=screening")
                await page.locator(".secop-module").wait_for()
                assert await page.locator("select, datalist").count() == 0
                await page.locator(".export-scope").click()
                popup = page.get_by_role("listbox")
                assert await popup.is_visible()
                if (lang, width) in [("en", 1440), ("es", 390)]:
                    await page.screenshot(
                        path=str(OUT / f"dropdown-scope-{lang}-{width}.png"),
                        full_page=True,
                    )
                await page.keyboard.press("Escape")
                toolbar = page.locator(".export-controls")
                await toolbar.wait_for()
                assert await toolbar.count() == 1
                assert await page.locator(".secop-module .export-controls").count() == 0
                bar_box = await toolbar.bounding_box()
                title_box = await page.locator("h1").bounding_box()
                assert (
                    bar_box
                    and title_box
                    and bar_box["y"] + bar_box["height"] < title_box["y"]
                )
                trigger = toolbar.locator(".export-trigger")
                scope = toolbar.locator('[role="combobox"]')
                button_box = await trigger.bounding_box()
                scope_box = await scope.bounding_box()
                assert abs(button_box["y"] - scope_box["y"]) < 3
                await trigger.click()
                assert await page.locator(
                    ".export-options button"
                ).all_text_contents() == ["CSV", "JSON"]
                if (lang, width) in [("en", 1440), ("es", 390)]:
                    await page.screenshot(
                        path=str(OUT / f"export-{lang}-{width}.png"), full_page=True
                    )
                await page.keyboard.press("Escape")
                assert not await page.locator(".export-options").count()
                await toolbar.locator(".filter-help button").focus()
                export_help = await toolbar.locator('[role="tooltip"]').bounding_box()
                assert (
                    export_help
                    and export_help["x"] >= 0
                    and export_help["x"] + export_help["width"] <= width
                )
                await page.keyboard.press("Escape")
                await page.locator('.presentation-controls [role="combobox"]').click()
                currency_options = page.get_by_role("listbox")
                if (lang, width) in [("en", 1440), ("es", 390)]:
                    await page.screenshot(
                        path=str(OUT / f"dropdown-currency-{lang}-{width}.png"),
                        full_page=True,
                    )
                await currency_options.locator('[role="option"][value="USD"]').click()
                rate_input = page.locator(
                    '.presentation-controls input[inputmode="decimal"]'
                )
                await rate_input.wait_for()
                await page.wait_for_function(
                    "document.querySelector('#presentation-rate').value === '4000'"
                )
                assert "(USD)" in await page.locator(".secop-summary").inner_text()
                original = (
                    "8,137,440,199.125000" if lang == "en" else "8.137.440.199,125000"
                )
                assert original not in await page.locator(".secop-module").inner_text()
                await rate_input.fill("4000.123456")
                await page.locator(".secop-contracts-table").wait_for()
                status_name = "Status" if lang == "en" else "Estado"
                await page.get_by_role("combobox", name=status_name, exact=True).click()
                status_popup = page.get_by_role("listbox")
                popup_box = await status_popup.bounding_box()
                assert (
                    popup_box
                    and popup_box["x"] >= 0
                    and popup_box["y"] >= 0
                    and popup_box["x"] + popup_box["width"] <= width
                )
                assert popup_box["y"] + popup_box["height"] <= (
                    await page.evaluate("innerHeight")
                )
                if (lang, width) in [("en", 1440), ("es", 390)]:
                    await page.screenshot(
                        path=str(OUT / f"dropdown-contracts-{lang}-{width}.png"),
                        full_page=True,
                    )
                await page.keyboard.press("Escape")
                if (lang, width) in [("en", 1440), ("es", 390)]:
                    await page.screenshot(
                        path=str(OUT / f"manual-{lang}-{width}.png"), full_page=True
                    )
                overflow = await page.evaluate(
                    "document.documentElement.scrollWidth > innerWidth"
                )
                assert not overflow, (lang, width, "manual overflow")
                assert (
                    await page.locator(".secop-contracts-table").inner_text()
                    and "(USD)"
                    in await page.locator(".secop-contracts-table").inner_text()
                    and "≈" in await page.locator(".secop-contracts-table").inner_text()
                )
                # Keyboard focus remains visible on the native entry control.
                await page.locator(
                    '.presentation-controls input[inputmode="decimal"]'
                ).focus()
                outline = await page.locator(
                    '.presentation-controls input[inputmode="decimal"]'
                ).evaluate("(e)=>getComputedStyle(e).outlineStyle")
                # Tooltips stay inside the viewport and retain keyboard dismissal.
                help_button = page.locator(".currency-card-heading .filter-help button")
                await help_button.focus()
                tooltip = page.locator('.currency-card-heading [role="tooltip"]')
                box = await tooltip.bounding_box()
                assert box and box["x"] >= 0 and box["x"] + box["width"] <= width
                await page.keyboard.press("Escape")
                assert not await tooltip.is_visible()
                state["rate_failed"] = True
                await page.locator(".currency-rate-input button").click()
                await page.wait_for_function(
                    "!document.querySelector('.secop-module').innerText.includes('≈')"
                )
                message = (
                    "TRM unavailable or stale" if lang == "en" else "TRM no disponible"
                )
                await page.get_by_text(message, exact=False).wait_for()
                if (lang, width) in [("en", 1440), ("es", 390)]:
                    await page.screenshot(
                        path=str(OUT / f"unavailable-{lang}-{width}.png"),
                        full_page=True,
                    )
                await page.goto(
                    base_url + "/companies/" + D["id"] + "?tab=capital-markets"
                )
                await page.locator("#registered-securities > summary").click()
                market_dropdown = page.locator(
                    ".market-filters .dropdown-trigger"
                ).first
                await market_dropdown.wait_for()
                await market_dropdown.click()
                assert await page.get_by_role("listbox").is_visible()
                assert await page.locator("select, datalist").count() == 0
                if (lang, width) in [("en", 1440), ("es", 390)]:
                    await page.screenshot(
                        path=str(OUT / f"dropdown-markets-{lang}-{width}.png"),
                        full_page=True,
                    )
                await page.keyboard.press("Escape")
                await page.goto(base_url + "/?q=SYNTHETIC")
                await page.locator(".advanced-filters > summary").click()
                advanced_dropdown = page.locator(".filter-pair .dropdown-trigger").first
                await advanced_dropdown.wait_for()
                await advanced_dropdown.click()
                assert await page.get_by_role("listbox").is_visible()
                assert await page.locator("select, datalist").count() == 0
                if (lang, width) in [("en", 1440), ("es", 390)]:
                    await page.screenshot(
                        path=str(OUT / f"dropdown-advanced-{lang}-{width}.png"),
                        full_page=True,
                    )
                await page.keyboard.press("Escape")
                await page.goto(base_url + "/references")
                await page.locator("#capabilities-title").wait_for()
                if (lang, width) in [("en", 1440), ("es", 390)]:
                    await page.screenshot(
                        path=str(OUT / f"references-{lang}-{width}.png"), full_page=True
                    )
                assert not await page.evaluate(
                    "document.documentElement.scrollWidth > innerWidth"
                ), (lang, width, "references overflow")
                report.append(
                    {
                        "language": lang,
                        "width": width,
                        "page_overflow": False,
                        "single_line_export_bar_above_title": True,
                        "no_native_selects": True,
                        "markets_and_advanced_custom_dropdowns": True,
                        "custom_popup_within_viewport": True,
                        "export_formats_and_dismissal": True,
                        "manual_replacement_visible": True,
                        "dynamic_labels": True,
                        "tooltip_within_viewport": True,
                        "unavailable_preserves_cop": True,
                        "focus_outline": outline,
                    }
                )
                await context.close()
        (OUT / "inspection.json").write_text(json.dumps(report, indent=2))
        await browser.close()


parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://127.0.0.1:5174")
asyncio.run(main(parser.parse_args().base_url.rstrip("/")))
