"""Capture actual React components against a verified API snapshot with original displayed values."""
import asyncio,json,argparse
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]
D=json.loads((ROOT/'fixtures/ecopetrol.json').read_text())
ID=D['profile']['id']

async def main(base):
    out=ROOT/'captures';out.mkdir(exist_ok=True)
    manifest={}
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        page=await browser.new_page(viewport={'width':1600,'height':1100},device_scale_factor=2,locale='es-CO',reduced_motion='reduce')
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        async def route(r):
            u=urlparse(r.request.url);path=u.path
            if path.endswith('/parameters'):
                # Existing app's bundled catalog; never fabricate source labels.
                await r.continue_();return
            if path.endswith('/capital-markets'):body=D['markets']
            elif path.endswith('/securities'):body=D['securities']
            elif path.endswith('/secop') or path.endswith('/secop/refresh'):body=D['secop']
            elif path.endswith('/contracts'):
                body=D['contracts_page2'] if parse_qs(u.query).get('page',['1'])[0]=='2' else D['contracts']
            elif '/contracts/' in path:body=D['detail']
            elif path.endswith('/sources'):body=D['records']
            elif path.endswith('/companies'):body=D['search']
            else:body=D['profile']
            await r.fulfill(json=body)
        await page.route('**/api/v1/**',route)
        async def shot(name,locator):
            await locator.scroll_into_view_if_needed();await page.wait_for_timeout(140)
            await locator.screenshot(path=str(out/(name+'.png')))
            box=await locator.bounding_box();manifest[name]={'file':name+'.png','width':round(box['width']),'height':round(box['height']),'company_id':ID,'data':'recorded public-source API evidence; not synthetic'}
        async def clip(name,locators):
            boxes=[await x.bounding_box() for x in locators];x=min(b['x'] for b in boxes);y=min(b['y'] for b in boxes);right=max(b['x']+b['width'] for b in boxes);bottom=max(b['y']+b['height'] for b in boxes)
            await page.screenshot(path=str(out/(name+'.png')),clip={'x':x,'y':y,'width':right-x,'height':bottom-y})
            manifest[name]={'file':name+'.png','width':round(right-x),'height':round(bottom-y),'company_id':ID,'data':'recorded public-source API evidence; not synthetic'}
        await page.goto(base)
        await page.locator('.search-form').wait_for()
        await shot('home',page.locator('.hero'))
        for text in ['E','ECOP','ECOPETROL']:
            await page.locator('#company-search').fill(text)
            await shot('typing-'+str(len(text)),page.locator('.search-control'))
        await shot('typing',page.locator('.hero'))
        await shot('typing-gif',page.locator('.search-control'))
        await page.locator('.search-submit').first.click()
        row=page.locator('tr').filter(has=page.locator(f'a.company-link[href="/companies/{ID}"]'))
        await row.wait_for()
        await shot('search',page.locator('.search-table-wrap'))
        await row.scroll_into_view_if_needed()
        await clip('result-gif',[row.locator('td').nth(0),row.locator('td').nth(1)])
        await row.locator('a.company-link').click()
        await page.locator('.profile-grid').wait_for()
        await shot('overview-tabs',page.locator('.tabs'))
        await shot('identity',page.locator('.profile-heading'))
        await shot('identity-gif',page.locator('.profile-grid .panel').first)
        await shot('overview',page.locator('.profile-grid'))
        source=page.locator('.data-source-information')
        await source.locator(':scope > summary').click()
        await page.locator('.source-freshness').scroll_into_view_if_needed()
        await clip('rues-source',[page.locator('.source-provider').first,page.locator('.source-freshness')])
        await page.get_by_role('link',name='Mercado de capitales',exact=True).click()
        await page.locator('.market-issuer').wait_for()
        await shot('issuer-tabs',page.locator('.tabs'))
        await shot('issuer',page.locator('.market-issuer').first.locator('..'))
        await shot('issuer-gif',page.locator('.market-issuer').first.locator('..'))
        await page.get_by_role('heading',name='Valores registrados (5)',exact=True).click()
        await page.locator('.instruments-table tbody tr').first.wait_for()
        await shot('securities',page.locator('#registered-securities'))
        # Only official RNVE registration / securities are captured. Never capture quote panels.
        await page.get_by_role('link',name='Contratos con el Gobierno',exact=True).click()
        await page.locator('.secop-summary').wait_for()
        await shot('secop-tabs',page.locator('.tabs'))
        await shot('secop',page.locator('.secop-header-with-summary'))
        await shot('secop-gif',page.locator('.secop-summary'))
        await shot('activity',page.locator('.secop-module > .profile-grid'))
        await page.get_by_role('button',name=D['detail']['contract_id'],exact=True).click()
        await page.locator('.secop-detail dl').wait_for()
        await shot('evidence',page.locator('.secop-detail'))
        # Wider first portion of detail is also available for a gentle camera pan.
        assert not errors,errors
        await browser.close()
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print('Captured',len(manifest),'actual UI elements; quote prices excluded.')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base-url',default='http://127.0.0.1:5173');args=parser.parse_args();asyncio.run(main(args.base_url))
