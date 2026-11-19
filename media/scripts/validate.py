"""Fail on incorrect export specs, entity association, partial totals or invalid cues."""
import json,subprocess,hashlib
from pathlib import Path
from decimal import Decimal
from PIL import Image,ImageChops
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'exports';report={}
d=json.loads((ROOT/'fixtures/ecopetrol.json').read_text());rows=d['contracts']['items']+d['contracts_page2']['items']
assert d['profile']['nit']=='899999068' and str(d['profile']['verification_digit'])=='1'
assert len(rows)==7 and len({r['contract_id'] for r in rows})==7
for r in rows:assert r['match_status']=='verified' and r['normalized_supplier_identifier']=='899999068'
total=sum((Decimal(str(r['value'])) for r in rows if r['value'] is not None),Decimal(0));assert total==Decimal('8137440199')
summary=d['secop']['summary']
assert summary['total_contracts']==len(rows)
assert Decimal(summary['total_values']['COP'])==total
assert summary['distinct_buyers']==len({r['buyer'] for r in rows})==5
assert all(r['currency']=='COP' for r in rows)
assert summary['latest_signature_date']==max(r['signature_date'] for r in rows if r['signature_date'])
assert d['detail']['contract_id']=='CO1.PCCNTR.8317598'
assert d['detail']['contract_id'] in {r['contract_id'] for r in rows}
report['evidence']={'company_id':d['profile']['id'],'nit':d['profile']['nit'],'unique_contracts':len(rows),'reconciled_cop':str(total)}
for n,secs in [('promo',30),('walkthrough',60)]:
    p=OUT/f'colombia-company-intelligence-{n}-{secs}s.mp4'
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)]))
    v=next(s for s in info['streams'] if s['codec_type']=='video');a=next(s for s in info['streams'] if s['codec_type']=='audio');s=next(s for s in info['streams'] if s['codec_type']=='subtitle')
    assert (v['width'],v['height'],v['codec_name'],v['avg_frame_rate'],v['pix_fmt'])==(1920,1080,'h264','30/1','yuv420p')
    assert int(v['nb_frames'])==secs*30 and abs(float(info['format']['duration'])-secs)<.05
    assert a['codec_name']=='aac' and a['channels']==2 and s['tags']['language']=='spa'
    cues=json.loads((ROOT/f'captions/{n}.json').read_text());last=0
    for c in cues:assert last<=c['start']<c['end']<=secs;last=c['end']
    # Full decode catches corrupt frames / incomplete files, including final GOP.
    subprocess.run(['ffmpeg','-v','error','-i',str(p),'-f','null','-'],check=True)
    measured=subprocess.run(['ffmpeg','-hide_banner','-i',str(p),'-vn','-af','loudnorm=I=-16:TP=-1.5:LRA=9:print_format=json','-f','null','-'],capture_output=True,text=True,check=True).stderr
    levels=json.JSONDecoder().raw_decode(measured[measured.rfind('{'):])[0];assert float(levels['input_tp'])<=-.9
    report[n]={'duration':info['format']['duration'],'video':{k:v[k] for k in ['codec_name','width','height','avg_frame_rate','nb_frames']},'audio':{k:a[k] for k in ['codec_name','sample_rate','channels']},'loudness_lufs':levels['input_i'],'true_peak_dbtp':levels['input_tp'],'captions':len(cues),'bytes':p.stat().st_size,'fully_decoded':True}
p=OUT/'colombia-company-intelligence-demo.gif';im=Image.open(p);assert im.size==(1000,620) and im.info['loop']==0
first=im.convert('RGB');duration=0
for i in range(im.n_frames):im.seek(i);duration+=im.info.get('duration',0)
last=im.convert('RGB');assert 11800<=duration<=12200
# Small cursor/zoom differences are acceptable; there must be no end-card jump.
from PIL import ImageStat
diff=ImageChops.difference(first,last);mean=sum(ImageStat.Stat(diff).mean)/3
assert mean<10
report['gif']={'size':list(im.size),'frames':im.n_frames,'duration_ms':duration,'loop':0,'bytes':p.stat().st_size,'first_last_mean_difference':round(mean,3)}
poster=Image.open(OUT/'colombia-company-intelligence-poster.png');assert poster.size==(1920,1080)
report['poster']={'size':list(poster.size)}
report['sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.suffix in ['.mp4','.gif','.png']}
(ROOT/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
