"""Render the real frontend with isolated synthetic API evidence; no live supplier calls.

Run with backend/.venv/bin/python scripts/design_review.py --phase before|after.
The dev frontend must already be running at --base-url (default localhost:5173).
Screenshots and a machine-readable inspection report go under docs/design/assets/.
"""

import argparse
import asyncio
import copy
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "docs/design/fixtures/ui-review.json").read_text())
ID = DATA["id"]


async def review_context(browser, args, out, report, lang, device, width):
    context = await browser.new_context(
        locale="en-US" if lang == "en" else "es-CO",
        viewport={"width": width, "height": 1000 if width > 700 else 844},
        reduced_motion="reduce",
    )
    scenario = {"state": "normal"}
    loading_gate = asyncio.Event()

    async def route(r):
        u = urlparse(r.request.url)
        path = u.path
        params = parse_qs(u.query)
        if scenario["state"] == "loading" and path.endswith("/companies"):
            await loading_gate.wait()
        if scenario["state"] == "error" and path.endswith("/companies"):
            await r.fulfill(
                status=503,
                json={
                    "error": {
                        "code": "source_timeout",
                        "message": "Synthetic upstream timeout",
                    }
                },
            )
            return
        if path.endswith("/parameters"):
            body = DATA["catalog"]
        elif path.endswith("/platform"):
            body = DATA["platform"]
        elif path.endswith("/capital-markets"):
            body = DATA["markets"]
        elif path.endswith("/securities"):
            body = {
                "items": [DATA["instrument"]],
                "total": 1,
                "unfiltered_total": 1,
                "page": 1,
                "page_size": 10,
                "has_more": False,
                "availability": "available",
            }
        elif path.endswith("/secop"):
            body = copy.deepcopy(DATA["secop"])
            if scenario["state"] == "stale":
                body.update(
                    outcome="stale",
                    error_code="source_timeout",
                    cache_age_seconds=90000,
                )
        elif path.endswith("/contracts"):
            page = int(params.get("page", ["1"])[0])
            start = (page - 1) * 5
            body = {
                "items": DATA["contracts"][start : start + 5],
                "total": 7,
                "page": page,
                "page_size": 5,
                "has_more": page == 1,
                "run_id": ID,
            }
        elif "/contracts/" in path:
            body = DATA["contracts"][0]
        elif path.endswith("/sources"):
            body = DATA["records"]
        elif path.endswith("/companies"):
            body = {
                "items": []
                if scenario["state"] == "empty"
                else [
                    dict(
                        DATA["company"],
                        chamber="CÁMARA SINTÉTICA",
                        registration_number="00123",
                        registration_date="20200115",
                        renewal_date="20260218",
                        match_type="exact_nit",
                        evidence=[],
                        data_source="rues",
                        registered_bvc=True,
                    )
                ],
                "page": 1,
                "page_size": 20,
                "has_more": False,
                "stale": False,
                "warning": None,
            }
        else:
            body = DATA["company"]
        await r.fulfill(json=body)

    await context.route("**/api/v1/**", route)
    page = await context.new_page()
    page.on("pageerror", lambda e: report["browser_errors"].append(str(e)))

    async def capture(name, url, selector, action=None, state="normal"):
        scenario["state"] = state
        await page.goto(args.base_url + url)
        await page.locator(selector).first.wait_for()
        if action:
            await action()
        await page.evaluate("document.fonts.ready")
        await page.wait_for_timeout(70)
        measurements = await page.evaluate(
            """() => ({overflow:document.documentElement.scrollWidth > innerWidth,lang:document.documentElement.lang,smallTargets:[...document.querySelectorAll('button,a,input,select,summary')].filter(e=>e.getClientRects().length && getComputedStyle(e).visibility!=='hidden' && !e.disabled).map(e=>({text:(e.getAttribute('aria-label')||e.textContent||e.tagName).trim().slice(0,70),w:Math.round(e.getBoundingClientRect().width),h:Math.round(e.getBoundingClientRect().height)})).filter(e=>e.w<24||e.h<24)})"""
        )
        save = (lang == "en" and device == "desktop") or (
            lang == "es" and device == "mobile"
        )
        filename = f"{name}-{lang}-{device}.png"
        if save:
            await page.screenshot(path=str(out / filename), full_page=True)
        report["screens"].append(
            dict(
                name=name,
                language=lang,
                viewport=device,
                screenshot=filename if save else None,
                **measurements,
            )
        )
        if args.phase == "after":
            assert not measurements["overflow"], f"Overflow: {name} {lang} {device}"

    await capture("home", "/", ".search-form")
    if args.phase == "after":
        await page.keyboard.press("Tab")
        assert await page.locator(".skip-link").evaluate(
            "(e)=>e===document.activeElement"
        )
        await page.keyboard.press("Enter")
        assert await page.locator("main").evaluate("(e)=>e===document.activeElement")
        await page.keyboard.press("Tab")
        assert await page.locator("#company-search").evaluate(
            "(e)=>e===document.activeElement"
        )
        assert (
            await page.locator(".search-control").evaluate(
                "(e)=>getComputedStyle(e).outlineStyle"
            )
            == "solid"
        )
        info = page.locator(".bvc-search-filter .filter-help button")
        await info.focus()
        tooltip = page.locator(".bvc-search-filter [role=tooltip]")
        assert await tooltip.is_visible()
        assert (await info.bounding_box())["width"] >= 32
        await info.press("Escape")
        assert not await tooltip.is_visible()
        await page.locator("#company-search").fill("ANDINOS")
        await page.locator("#company-search").press("Enter")
        await page.locator(".company-link").wait_for()
        await page.locator(".company-link").click()
        assert f"/companies/{ID}" in page.url
        await page.get_by_role(
            "heading", name=DATA["company"]["legal_name"], exact=True
        ).wait_for()

    if args.phase == "after":
        contrast = await page.evaluate(r"""() => {
          const rgb = value => (value.match(/[\d.]+/g) || []).slice(0,3).map(Number);
          const luminance = value => rgb(value).map(x => x/255).map(x => x <= .04045 ? x/12.92 : ((x+.055)/1.055)**2.4).reduce((sum,x,i) => sum+x*[.2126,.7152,.0722][i],0);
          return [...document.querySelectorAll('dt, .muted, .small, .text-link, .badge')].filter(e => e.checkVisibility() && e.textContent.trim()).map(e => {
            let node=e; let bg='rgb(247,248,247)';
            while(node){ const c=getComputedStyle(node).backgroundColor; if(c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent'){bg=c;break;} node=node.parentElement; }
            const fg=getComputedStyle(e).color; const [lo,hi]=[luminance(fg),luminance(bg)].sort((a,b)=>a-b);
            return {text:e.textContent.trim().slice(0,50), foreground:fg, background:bg, ratio:(hi+.05)/(lo+.05)};
          });
        }""")
        report.setdefault("contrast_samples", []).extend(contrast)
        assert all(sample["ratio"] >= 4.5 for sample in contrast), contrast
    await capture("results", "/?q=ANDINOS", ".company-link")
    await capture("overview", f"/companies/{ID}", ".profile-grid")

    async def sources():
        await page.locator(".data-source-information > summary").click()
        await page.locator(".source-records .source-disclosure > summary").first.click()
        await page.locator(".record-fields > summary").first.click()

    await capture("sources", f"/companies/{ID}", ".data-source-information", sources)

    async def securities():
        await page.get_by_role(
            "heading",
            name="Registered securities (1)"
            if lang == "en"
            else "Valores registrados (1)",
        ).click()
        await page.locator(".instruments-table tbody tr").first.wait_for()

    await capture(
        "markets",
        f"/companies/{ID}?tab=capital-markets",
        ".bvc-price",
        securities,
    )
    await capture(
        "secop",
        f"/companies/{ID}?tab=screening",
        ".secop-contracts-table tbody tr",
    )
    if args.phase == "after":
        for value in [
            DATA["contract"]["buyer"].upper(),
            DATA["contract"]["raw_status"].upper(),
            DATA["contract"]["modality"].upper(),
            DATA["contract"]["description"],
        ]:
            assert await page.get_by_role("cell", name=value, exact=True).count() == 5
        summary_text = (await page.locator(".secop-summary").text_content()).replace(
            "\u00a0", " "
        )
        assert (
            "8,137,440,199.125000" if lang == "en" else "8.137.440.199,125000"
        ) in summary_text
        for metric in await page.locator(".fit-metric-value").all():
            assert await metric.evaluate(
                "e => getComputedStyle(e).whiteSpace === 'nowrap' && e.scrollWidth <= e.clientWidth + 1"
            )
            assert await metric.locator("span").evaluate(
                "e => e.getBoundingClientRect().width <= e.parentElement.clientWidth + 1"
            )
        assert await page.locator(".secop-sort-control .dropdown-trigger").evaluate(
            "e => getComputedStyle(e).fontSize"
        ) == await page.locator(
            ".market-filters label .dropdown-trigger"
        ).first.evaluate("e => getComputedStyle(e).fontSize")
        assert (
            await page.locator(".secop-bars").first.evaluate(
                "e => parseFloat(getComputedStyle(e).paddingInlineEnd)"
            )
            >= 20
        )
        if lang == "es":
            assert (
                await page.get_by_role(
                    "link", name="Contratos con el Gobierno", exact=True
                ).count()
                == 1
            )
            assert (
                await page.get_by_role(
                    "heading",
                    name="Top cinco entidades por valor contractual (COP)",
                    exact=True,
                ).count()
                == 1
            )
            assert (
                await page.get_by_text(
                    "Valores contractuales reportados, no representan pagos ni ingresos.",
                    exact=True,
                ).count()
                == 1
            )
        await page.get_by_role(
            "button",
            name="Next →" if lang == "en" else "Siguiente →",
            exact=True,
        ).click()
        await page.get_by_role("button", name="CO1.SYNTHETIC-7", exact=True).wait_for()
        assert await page.locator(".secop-contracts-table tbody tr").count() == 2

    async def detail():
        await page.get_by_role("button", name="CO1.SYNTHETIC-1", exact=True).click()
        await page.locator(".secop-detail dl").wait_for()

    await capture(
        "contract-detail",
        f"/companies/{ID}?tab=screening",
        ".secop-contracts-table tbody tr",
        detail,
    )
    await capture("parameters", "/parameters", ".parameter-table")
    await capture("references", "/references", ".platform-counts")
    await capture("empty", "/?q=NOTFOUND", ".empty", state="empty")
    await capture("error", "/?q=ERROR", "[role=alert]", state="error")
    await capture("loading", "/?q=LOADING", "dialog[open]", state="loading")
    if args.phase == "after":
        await page.keyboard.press("Escape")
        assert await page.locator("dialog[open]").count() == 0
        assert await page.locator(".search-loading-inline").is_visible()
        assert (
            await page.locator(".search-loading-animation").evaluate(
                "(e)=>getComputedStyle(e).display"
            )
            == "none"
        )
    loading_gate.set()
    await page.locator(".company-link").wait_for()

    await capture(
        "stale",
        f"/companies/{ID}?tab=screening",
        ".secop-contracts-table tbody tr",
        state="stale",
    )
    await context.close()


async def run(args):
    out = ROOT / "docs/design/assets" / args.phase
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "phase": args.phase,
        "data": "synthetic API fixtures; actual application rendering",
        "screens": [],
        "browser_errors": [],
    }
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for lang in ["en", "es"]:
            for device, width in [("desktop", 1440), ("mobile", 390)]:
                await review_context(browser, args, out, report, lang, device, width)
        await browser.close()
    (out / "inspection.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    assert not report["browser_errors"], report["browser_errors"]
    print(
        f"{args.phase}: {len(report['screens'])} rendered cases; {sum(bool(s['screenshot']) for s in report['screens'])} screenshots; report: {out / 'inspection.json'}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["before", "after"], required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    asyncio.run(run(parser.parse_args()))
