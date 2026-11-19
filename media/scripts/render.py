"""Deterministic native-brand compositions; real UI pixels are never re-typeset."""
import json,subprocess,math,argparse
from pathlib import Path
from functools import lru_cache
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'exports';OUT.mkdir(exist_ok=True)
STORY=json.loads((ROOT/'src/story.json').read_text());MANIFEST=json.loads((ROOT/'captures/manifest.json').read_text());BG='#f7f8f7';INK='#17333c';GREEN='#285f4b';MUTED='#52665f'
FONT='/System/Library/Fonts/Avenir Next.ttc'
@lru_cache(None)
def font(size,bold=False):return ImageFont.truetype(FONT,size,index=2 if bold else 7)
@lru_cache(None)
def capture(name):return Image.open(ROOT/f'captures/{name}.png').convert('RGB')
def ease(x):return (1-math.cos(math.pi*min(1,max(0,x))))/2
def text(d,xy,s,size=36,fill=INK,bold=False):d.text(xy,s,font=font(size,bold),fill=fill,spacing=12)
def wrapped(d,s,width,size):
    lines=[];line=''
    for w in s.split():
        v=(line+' '+w).strip()
        if d.textlength(v,font=font(size))>width and line:lines.append(line);line=w
        else:line=v
    return lines+[line]
def pointer(im,x,y,click=False,scale=1):
    d=ImageDraw.Draw(im);r=round(20*scale)
    if click:d.ellipse((x-r,y-r,x+r,y+r),outline='#167c72',width=max(2,round(3*scale)))
    pts=[(x,y),(x+4*scale,y+25*scale),(x+10*scale,y+18*scale),(x+18*scale,y+30*scale),(x+23*scale,y+27*scale),(x+15*scale,y+15*scale),(x+25*scale,y+14*scale)]
    d.polygon(pts,fill='white',outline=INK,width=2)
def panel(im,name,box,p,small=False):
    x,y,w,h=box;d=ImageDraw.Draw(im);d.rounded_rectangle((x-1,y-35,x+w+1,y+h+1),16,fill='white',outline='#dce3df',width=2)
    text(d,(x+20,y-28),'Colombia Company Intelligence',16 if small else 20,fill=MUTED)
    for j in range(3):d.ellipse((x+w-65+j*15,y-22,x+w-58+j*15,y-15),fill='#dce3df')
    src=capture(name);dpr=src.width/MANIFEST[name]['width']
    if small and name in ['issuer-gif','identity-gif']:src=src.crop((0,0,src.width, min(src.height,round(340*dpr))))
    sw,sh=src.size
    # Preserve wide screens at legible width; tall evidence scrolls top to bottom.
    scale=min((w-30)/sw,(h-24)/sh)
    if name=='issuer' and not small:scale=1.62/dpr
    elif sh/dpr>800 and not small:scale=(w-30)/sw
    elif small:scale=min((w-32)/sw,(h-24)/sh)
    scale*=1+.018*ease(p);nw,nh=round(sw*scale),round(sh*scale)
    resized=src.resize((nw,nh),Image.Resampling.LANCZOS)
    cropy=round(max(0,nh-h+16)*ease(p))
    pane=Image.new('RGB',(w,h),'white');pane.paste(resized,(35 if name=='issuer' and not small else (w-nw)//2, max(10,(h-nh)//2) if nh<=h else 8-cropy));im.paste(pane,(x,y))
    if name=='issuer' and not small:
        q=ImageDraw.Draw(im);text(q,(x+1040,y+150),'CLAVE DE LECTURA',23,fill=GREEN,bold=True)
        text(q,(x+1040,y+210),'Emisor registrado.',40,bold=True)
        text(q,(x+1040,y+270),'Identidad verificada por NIT.',29)
        text(q,(x+1040,y+350),'El registro no demuestra',29,fill=MUTED)
        text(q,(x+1040,y+393),'negociación vigente ni liquidez.',29,fill=MUTED)
    if name.startswith('typing'):
        px=x+w*.78;py=y+h*.69
    elif name=='search':px=x+w*.2;py=y+h*.83
    elif name=='evidence':px=x+w*.62;py=y+h*.75
    else:px=x+w*.94;py=y+h*.91
    px-=25*(1-ease(p));pointer(im,px,py,click=name=='search' and .82<p<.93,scale=.7 if small else 1)
def base(s,p,small=False):
    w,h=(1000,620) if small else (1920,1080);im=Image.new('RGB',(w,h),BG);d=ImageDraw.Draw(im)
    if small:
        d.rectangle((0,0,w,70),fill='black');text(d,(30,17),'Colombia Company Intelligence',25,fill='white',bold=True)
        text(d,(35,89),s['title'],30,bold=True)
        name=s['capture']
        if name=='typing-gif':name=['typing-1','typing-4','typing-9'][min(2,int(p*5))]
        panel(im,name,(35,178,930,347),p,True)
        text(ImageDraw.Draw(im),(35,555),'ECOPETROL S A · NIT 899999068-1',20,bold=True)
        text(ImageDraw.Draw(im),(35,587),'Consulta reproducida · registros oficiales · 19 nov 2026',16,fill=MUTED)
        return im
    kind=s.get('kind');text(d,(80,38),s.get('kicker',''),22,fill=GREEN,bold=True)
    if kind in ['closing','problem']:
        d.rounded_rectangle((80,138,1840,898),28,fill=INK if kind=='closing' else 'white',outline='#dce3df',width=2)
        fg='white' if kind=='closing' else INK
        text(d,(145,220),s['title'],76,fill=fg,bold=True)
        if kind=='closing':
            logo=Image.open(ROOT.parent/'frontend/public/colombia-network-logo.png').convert('RGBA');logo.thumbnail((310,310));im.paste(logo,(1430,290),logo)
            text(d,(145,498),'Colombia Company Intelligence',44,fill='white',bold=True)
            text(d,(145,588),'github.com/molartep/colombia-company-intelligence',30,fill='#dce3df')
            text(d,(145,704),'Identidad · Mercado de capitales · Contratos del Gobierno',28,fill='#dce3df')
        else:
            for i,(name,sub) in enumerate([('RUES','Identidad y registro'),('SFC · RNVE','Emisores y valores'),('SECOP II','Contratos públicos')]):
                x=145+i*550;off=round(12*math.sin(p*math.pi+i))
                d.rounded_rectangle((x,530+off,x+505,750+off),20,fill=BG,outline='#dce3df',width=2)
                text(d,(x+28,568+off),name,40,bold=True);text(d,(x+28,642+off),sub,27,fill=MUTED)
    else:
        text(d,(80,84),s['title'],52,bold=True)
        name=s['capture']
        # Promo also explicitly shows the implemented RNVE feature.
        if name=='overview' and s['start']==10 and p>.57:name='issuer'
        if name=='typing':
            if p<.52:name=['typing-1','typing-4','typing-9'][min(2,int(p*6))]
        tabs='issuer-tabs' if name in ['issuer','securities'] else 'secop-tabs' if name in ['secop','activity','evidence'] else 'overview-tabs'
        if name not in ['search','typing','typing-1','typing-4','typing-9']:
            nav=capture(tabs);ratio=min(1760/nav.width,60/nav.height);nav=nav.resize((round(nav.width*ratio),round(nav.height*ratio)),Image.Resampling.LANCZOS);im.paste(nav,(80,167))
            panel(im,name,(80,280,1760,595),p)
        else:panel(im,name,(80,225,1760,650),p)
    d=ImageDraw.Draw(im);text(d,(80,895),'CONSULTA REPRODUCIDA · ECOPETROL S A · 19 NOV 2026 · FECHAS POR FUENTE',20,fill=MUTED)
    return im
def scene_at(spec,t):return next((s for s in spec['scenes'] if s['start']<=t<s['end']),spec['scenes'][-1])
def frame(spec,t,cues,small=False):
    s=scene_at(spec,t);p=(t-s['start'])/(s['end']-s['start'])
    if small and s['start']==11.3:p=0
    im=base(s,p,small)
    fade=.24 if small else .28
    if t-s['start']<fade and s['start']>0:
        prev=scene_at(spec,s['start']-.001);before=base(prev,1,small);im=Image.blend(before,im,ease((t-s['start'])/fade))
    d=ImageDraw.Draw(im)
    if not small:
        cue=next((c for c in cues if c['start']<=t<c['end']),None)
        if cue:
            lines=wrapped(d,cue['text'],1640,34);y=943 if len(lines)==1 else 927
            for line in lines:
                size=d.textbbox((0,0),line,font=font(34));tw=d.textlength(line,font=font(34));x=(1920-tw)/2
                d.rounded_rectangle((x-18,y-2,x+tw+18,y+48),8,fill=INK);text(d,(x,y),line,34,fill='white');y+=48
        d.rectangle((80,1052,1840,1056),fill='#dce3df');d.rectangle((80,1052,80+1760*t/spec['duration'],1056),fill=GREEN)
    return im
def render(name):
    small=name=='gif';spec=STORY[name];fps=15 if small else 30;w,h=(1000,620) if small else (1920,1080)
    cues=[] if small else json.loads((ROOT/f'captions/{name}.json').read_text())
    prefix='colombia-company-intelligence-';target=OUT/(prefix+('demo-source.mp4' if small else f'{name}-{spec["duration"]}s.mp4'))
    args=['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}','-r',str(fps),'-i','-']
    if not small:args+=['-i',str(ROOT/f'audio/{name}-mix.flac'),'-i',str(ROOT/f'captions/{name}.srt')]
    args+=['-map','0:v']
    if not small:args+=['-map','1:a','-map','2:s','-c:a','aac','-b:a','192k','-ar','48000','-af','loudnorm=I=-16:TP=-1.5:LRA=9','-c:s','mov_text','-metadata:s:s:0','language=spa']
    args+=['-c:v','libx264','-preset','fast','-crf','20','-threads','4','-pix_fmt','yuv420p','-movflags','+faststart','-t',str(spec['duration']),str(target)]
    proc=subprocess.Popen(args,stdin=subprocess.PIPE)
    for i in range(spec['duration']*fps):
        f=frame(spec,i/fps,cues,small);proc.stdin.write(f.tobytes())
        if i% (fps*5)==0:print(name,round(i/fps),'s',flush=True)
        if name=='promo' and i==17*fps:f.save(OUT/(prefix+'poster.png'))
        if i in [fps*2,fps*12,fps*17,fps*28] and not small:f.save(OUT/f'{name}-review-{i//fps}.png')
    proc.stdin.close();assert proc.wait()==0
    if small:
        subprocess.run(['ffmpeg','-y','-v','error','-i',str(target),'-filter_complex','[0:v]split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle','-loop','0',str(OUT/(prefix+'demo.gif'))],check=True)
        target.unlink()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('asset',choices=['promo','walkthrough','gif','all'],default='all',nargs='?');a=p.parse_args()
    for n in (['promo','walkthrough','gif'] if a.asset=='all' else [a.asset]):render(n)
