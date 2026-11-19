"""Bounded extraction of one existing source-backed company; no data is fabricated."""
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode, quote

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:8000/api/v1'
COMPANY_ID = 'b02c94b3-d93f-4d9f-8ab9-f0ff51d97052'

def get(path):
    with urlopen(BASE+path,timeout=160) as response:
        return json.load(response)

def main():
    prefix=f'/companies/{COMPANY_ID}'
    # Saved API responses collected during production; recollect with this script when needed.
    paths={'search':'/companies?'+urlencode({'q':'ecopetrol'}),'profile':prefix,'records':prefix+'/sources','markets':prefix+'/capital-markets','securities':prefix+'/securities?page=1&page_size=10','secop':prefix+'/screening/secop','contracts':prefix+'/screening/secop/contracts?page=1&page_size=5'}
    result={name:get(path) for name,path in paths.items()}
    assert result['profile']['nit']=='899999068' and result['profile']['verification_digit']=='1'
    assert result['markets']['rnve']['match_status']=='verified'
    assert result['secop']['outcome'] in ['completed_with_matches','stale']
    assert result['contracts']['total']<=10, 'Media capture is deliberately bounded to ten contracts.'
    if result['contracts']['has_more']:
        result['contracts_page2']=get(prefix+'/screening/secop/contracts?page=2&page_size=5')
    row=next(x for x in result['contracts']['items'] if x['value'] and x['value']!='0')
    result['detail']=get(prefix+'/screening/secop/contracts/'+quote(row['contract_id'],safe='')+'?'+urlencode({'run_id':result['secop']['run_id']}))
    for row in [*result['contracts']['items'],*result.get('contracts_page2',{}).get('items',[])]:
        assert row['normalized_supplier_identifier']=='899999068' and row['match_status']=='verified'
    result['provenance']={'captured_at':datetime.now(timezone.utc).isoformat(),'company_id':COMPANY_ID,'nit':'899999068','dv':'1','endpoints':paths,'synthetic':False,'playback':'API snapshot replay; loading delays accelerated; not live market data','prices':'Quote panels are not captured or used; no price redistribution rights assumed.'}
    result['markets']['exchange_listing']['quotes']=[]
    result['provenance']['omitted_fields']=['markets.exchange_listing.quotes (unfeatured price collection excluded; redistribution rights not established)']
    (ROOT/'fixtures/ecopetrol.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('Saved one verified company and bounded source evidence.')
if __name__=='__main__':main()
