"""Download the official Apache-2.0 Kokoro ONNX model release, outside Git."""
from pathlib import Path
import argparse,urllib.request,hashlib,json
p=argparse.ArgumentParser();p.add_argument('--destination',type=Path,default=Path('/tmp/cci-media-models'));a=p.parse_args();a.destination.mkdir(parents=True,exist_ok=True)
manifest=Path(__file__).resolve().parents[1]/'audio/manifest.json'
known=json.loads(manifest.read_text())['model_sha256'] if manifest.exists() else {}
for name in ['kokoro-v1.0.onnx','voices-v1.0.bin']:
    path=a.destination/name
    if not path.exists():urllib.request.urlretrieve('https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/'+name,path)
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if name in known:assert digest==known[name],f'Checksum mismatch: {name}'
    print(name,digest)
