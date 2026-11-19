"""Optional local intelligibility review; does not replace a human voice audition."""
import json,subprocess
import numpy as np
from pathlib import Path
from faster_whisper import WhisperModel
ROOT=Path(__file__).resolve().parents[1]
m=WhisperModel('base',device='cpu',compute_type='int8',download_root='/tmp/cci-whisper')
out={}
for n in ['promo','walkthrough']:
    pcm=subprocess.check_output(['ffmpeg','-v','error','-i',str(ROOT/f'audio/{n}-narration.flac'),'-ar','16000','-ac','1','-f','f32le','-'])
    segments,info=m.transcribe(np.frombuffer(pcm,dtype=np.float32),language='es',beam_size=5,word_timestamps=True)
    out[n]=[{'start':s.start,'end':s.end,'text':s.text,'avg_logprob':s.avg_logprob} for s in segments]
    print(n, '\n'.join(s['text'] for s in out[n]),flush=True)
(ROOT/'audio/speech-review.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
