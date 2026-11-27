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
            for width in [320, 390, 768, 1440]:
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
                grid = page.locator(".secop-insights-grid")
                assert await grid.locator(":scope > article").count() == 4
                boxes = [
                    await grid.locator(":scope > article").nth(i).bounding_box()
                    for i in range(4)
                ]
                assert all(boxes)
                assert (
                    max(box["width"] for box in boxes)
                    - min(box["width"] for box in boxes)
                    < 2
                )
                if width > 700:
                    assert abs(boxes[0]["y"] - boxes[1]["y"]) < 2
                    assert abs(boxes[2]["y"] - boxes[3]["y"]) < 2
                    assert boxes[2]["y"] > boxes[0]["y"]
                else:
                    assert all(boxes[i + 1]["y"] > boxes[i]["y"] for i in range(3))
                await card.scroll_into_view_if_needed()
                assert await card.get_by_role("spinbutton").input_value() == "24"
                for help_button in await card.locator(".filter-help button").all():
                    await help_button.focus()
                    tooltip = await help_button.locator("..").get_by_role("tooltip").bounding_box()
                    assert tooltip and tooltip["x"] >= 0 and tooltip["x"] + tooltip["width"] <= width, (lang, width, tooltip)
                await card.get_by_role("spinbutton").focus()
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
                for action in await dialog.locator(".popup-icon-action").all():
                    await action.focus()
                    box = await action.bounding_box()
                    expected = 44 if width <= 700 else 32
                    assert box and box["width"] == expected and box["height"] == expected
                    tooltip = action.locator("..").get_by_role("tooltip")
                    await tooltip.wait_for(state="visible")
                    tip = await tooltip.bounding_box()
                    assert tip and tip["x"] >= 0 and tip["x"] + tip["width"] <= width
                    assert await tooltip.inner_text() == await action.get_attribute("aria-label")
                assert not await dialog.evaluate("e=>e.scrollWidth>e.clientWidth")
                await page.screenshot(path=str(OUT / f"dialog-{lang}-{width}.png"))
                await page.mouse.click(1, 1)
                assert await page.locator("dialog[open]").count() == 0
                assert await trigger.evaluate("(e)=>e===document.activeElement")
                await trigger.click()
                await dialog.get_by_role("button", name="Close" if lang == "en" else "Cerrar", exact=True).click()
                assert await trigger.evaluate("(e)=>e===document.activeElement")
                await trigger.click()
                await page.keyboard.press("Escape")
                assert await trigger.evaluate("(e)=>e===document.activeElement")
                await card.locator(".involvement-outcome-button").nth(2).click()
                await dialog.locator(".involvement-selected-evidence").scroll_into_view_if_needed()
                await page.screenshot(path=str(OUT / f"evidence-{lang}-{width}.png"))
                await page.keyboard.press("Escape")
                await page.goto(
                    "http://127.0.0.1:5174/methodology/rae?demo=true&decision=recent_participation"
                )
                await page.locator(".involvement-selected-evidence").first.wait_for()
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
                        "backdrop_focus_return": True,
                        "tooltip_inside_viewport": True,
                        "default_lookback_months": 24,
                        "popup_icon_sizes_and_tooltips": True,
                        "close_icon_focus_return": True,
                        "equal_width_insight_cards": True,
                        "layout": "2x2" if width > 700 else "stacked",
                    }
                )
                await context.close()
        await browser.close()
    (OUT / "inspection.json").write_text(json.dumps(report, indent=2) + "\n")


asyncio.run(main())
