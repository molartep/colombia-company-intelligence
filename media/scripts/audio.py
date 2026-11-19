"""Licensed local neural narration plus original sample-free instrumental music."""
import os,json,argparse,hashlib
from pathlib import Path
import numpy as np
import soundfile as sf
import onnxruntime as ort
from kokoro_onnx import Kokoro
ROOT=Path(__file__).resolve().parents[1]
def stamp(t):
    n=round(t*1000);return f'{n//3600000:02}:{n//60000%60:02}:{n//1000%60:02},{n%1000:03}'
def music(seconds,sr):
    t=np.arange(seconds*sr)/sr;out=np.zeros_like(t)
    # Original four-chord progression, no recordings or third-party samples.
    for i,chord in enumerate([(146.832,174.614,220),(130.813,164.814,196),(110,130.813,164.814),(130.813,146.832,196)]):
        start=i*seconds/4;local=t-start;dur=seconds/4
        env=np.clip(local/1.2,0,1)*np.clip((dur-local)/1.2,0,1)
        pad=sum(np.sin(2*np.pi*f*t)+.12*np.sin(2*np.pi*2*f*t) for f in chord)/4
        out+=pad*env*.028
    for beat in np.arange(0,seconds,.8):
        u=t-beat;f=[293.665,349.228,440,392][int(beat/.8)%4]
        env=np.where(u>=0,np.exp(-np.maximum(u,0)*5),0)*np.clip(u/.02,0,1)
        out+=np.sin(2*np.pi*f*t)*env*.018
    return out*np.clip(t/1.2,0,1)*np.clip((seconds-t)/1.8,0,1)
def main(models):
    ort.disable_telemetry_events();story=json.loads((ROOT/'src/story.json').read_text())
    k=Kokoro(str(models/'kokoro-v1.0.onnx'),str(models/'voices-v1.0.bin'))
    report={'voice':story['voice'],'language':story['language'],'engine':'kokoro-onnx 0.4.9','model_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in models.iterdir() if p.suffix in ['.onnx','.bin']},'assets':{}}
    for name in ['promo','walkthrough']:
        spec=story[name];sr=24000;voice=np.zeros(sr*spec['duration'],np.float32);cues=[]
        for i,s in enumerate(spec['scenes']):
            a,rate=k.create(s['narration'],voice=story['voice'],speed=1.0,lang=story['language']);assert rate==sr
            active=np.flatnonzero(np.abs(a)>.004)
            if len(active):a=a[max(0,active[0]-1200):min(len(a),active[-1]+1800)]
            available=s['end']-s['start']-.35
            if len(a)/sr>available:raise ValueError(f'{name} scene {i} narration too long: {len(a)/sr:.2f} > {available:.2f}; edit script')
            begin=s['start']+.18;end=begin+len(a)/sr
            n=min(240,len(a)//2);a[:n]*=np.linspace(0,1,n);a[-n:]*=np.linspace(1,0,n)
            voice[round(begin*sr):round(begin*sr)+len(a)]=a
            # One caption per utterance: timing comes from the actual PCM samples.
            cues.append({'start':begin,'end':end,'text':s['narration']})
        peak=max(float(np.max(np.abs(voice))),.01);voice=voice/peak*.76
        bed=music(spec['duration'],sr);mixed=voice+bed
        stereo=np.column_stack([mixed,mixed]);sf.write(ROOT/f'audio/{name}-mix.flac',stereo,sr,subtype='PCM_24')
        sf.write(ROOT/f'audio/{name}-narration.flac',voice,sr,subtype='PCM_24');sf.write(ROOT/f'audio/{name}-music.flac',bed,sr,subtype='PCM_24')
        (ROOT/f'captions/{name}.srt').write_text('\n\n'.join(f'{i+1}\n{stamp(c["start"])} --> {stamp(c["end"])}\n{c["text"]}' for i,c in enumerate(cues))+'\n')
        (ROOT/f'captions/{name}.json').write_text(json.dumps(cues,ensure_ascii=False,indent=2)+'\n')
        report['assets'][name]={'duration':spec['duration'],'cues':len(cues),'peak':float(np.max(np.abs(stereo))),'scenes':len(spec['scenes'])}
    (ROOT/'audio/manifest.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--models',type=Path,default=Path(os.environ.get('CCI_TTS_MODELS','/tmp/cci-media-models')));main(p.parse_args().models)
