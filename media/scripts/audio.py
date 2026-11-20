"""V2: expressive licensed multilingual narration, original music, speech ducking."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
from models import MODEL, REVISION, download

INSTRUCTION = "Una voz femenina adulta de español latinoamericano neutro, cálida, segura y conversacional. Locución profesional de un vídeo de producto, ágil, clara, sin alargar vocales, con pausas breves y entonación natural."


def stamp(t):
    n = round(t * 1000)
    return f"{n // 3600000:02}:{n // 60000 % 60:02}:{n // 1000 % 60:02},{n % 1000:03}"


def music(seconds, sr):
    t = np.arange(round(seconds * sr)) / sr
    out = np.zeros_like(t)
    beat = 60 / 86
    chords = [
        (146.832, 184.997, 220, 277.183),
        (123.471, 146.832, 184.997, 220),
        (97.999, 123.471, 146.832, 184.997),
        (110, 138.591, 164.814, 220),
    ]
    for step, start in enumerate(np.arange(0, seconds, beat * 8)):
        u = t - start
        duration = beat * 8
        env = np.clip(u / 0.6, 0, 1) * np.clip((duration + 0.8 - u) / 1.0, 0, 1)
        chord = chords[step % 4]
        out += (
            sum(
                np.sin(2 * np.pi * f * t) + 0.15 * np.sin(2 * np.pi * 2 * f * t)
                for f in chord
            )
            * env
            * 0.007
        )
    for step, start in enumerate(np.arange(0, seconds, beat)):
        u = t - start
        f = chords[(step // 8) % 4][step % 4] * 2
        env = np.clip(u / 0.015, 0, 1) * np.exp(-np.maximum(u, 0) * 5.7) * (u >= 0)
        out += np.sin(2 * np.pi * f * t) * env * 0.012
    return out * np.clip(t / 1.1, 0, 1) * np.clip((seconds - t) / 1.1, 0, 1)


def main(preflight=False):
    import mlx.core as mx
    from mlx_audio.tts.utils import load_model

    story = json.loads((ROOT / "src/story.json").read_text())
    cache = ROOT / ".cache/narration-v2"
    cache.mkdir(parents=True, exist_ok=True)
    m = None
    clips = {}
    report = {
        "engine": "mlx-audio 0.6.7",
        "model": MODEL,
        "model_revision": REVISION,
        "voice": "Designed neutral Latin American Spanish female voice",
        "language": "Spanish",
        "instruction": INSTRUCTION,
        "rate_change": False,
        "assets": {},
    }
    too_long = []
    for name in ["promo", "walkthrough"]:
        spec = story[name]
        sr = 24000
        voice = np.zeros(sr * spec["duration"], np.float32)
        cues = []
        for i, c in enumerate(spec["narration"]):
            key = hashlib.sha256(
                (c["text"] + INSTRUCTION + MODEL).encode()
            ).hexdigest()[:20]
            path = cache / (key + ".flac")
            if not path.exists():
                if m is None:
                    m = load_model(download())
                mx.random.seed(42)
                result = list(
                    m.generate_voice_design(
                        text=c["text"],
                        language="Spanish",
                        instruct=INSTRUCTION,
                        temperature=0.4,
                        max_tokens=700,
                    )
                )
                a = np.concatenate([np.array(x.audio) for x in result])
                assert result[0].sample_rate == sr
                active = np.flatnonzero(np.abs(a) > 0.004)
                if len(active):
                    a = a[max(0, active[0] - 1440) : min(len(a), active[-1] + 2400)]
                sf.write(path, a, sr, subtype="PCM_24")
            a, rate = sf.read(path, dtype="float32")
            duration = len(a) / rate
            available = c["end"] - c["start"]
            print(
                name,
                i,
                round(duration, 3),
                "available",
                round(available, 2),
                flush=True,
            )
            if duration > available + 0.05:
                too_long.append(
                    {
                        "asset": name,
                        "clip": i,
                        "seconds": duration,
                        "available": available,
                    }
                )
                continue
            begin = c["start"]
            finish = begin + duration
            voice[round(begin * sr) : round(begin * sr) + len(a)] = a
            cues.append({"start": begin, "end": finish, "text": c["text"]})
        clips[name] = (voice, cues)
        report["assets"][name] = {"duration": spec["duration"], "cues": len(cues)}
    if too_long:
        print(json.dumps({"needs_shorter_copy": too_long}, indent=2))
        raise SystemExit(2)
    if preflight:
        return
    for name, (voice, cues) in clips.items():
        sr = 24000
        secs = story[name]["duration"]
        voice = voice / max(float(np.max(np.abs(voice))), 0.01) * 0.74
        # Smooth speech-aware ducking: music drops under every spoken phrase.
        envelope = np.convolve(np.abs(voice), np.ones(2400) / 2400, mode="same")
        duck = 1 - 0.6 * np.clip(envelope / 0.025, 0, 1)
        bed = music(secs, sr) * duck
        mixed = voice + bed
        sf.write(ROOT / f"audio/{name}-narration.flac", voice, sr, subtype="PCM_24")
        sf.write(ROOT / f"audio/{name}-music.flac", bed, sr, subtype="PCM_24")
        sf.write(
            ROOT / f"audio/{name}-mix.flac",
            np.column_stack([mixed, mixed]),
            sr,
            subtype="PCM_24",
        )
        (ROOT / f"captions/{name}.json").write_text(
            json.dumps(cues, ensure_ascii=False, indent=2) + "\n"
        )
        (ROOT / f"captions/{name}.srt").write_text(
            "\n\n".join(
                f"{i + 1}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}"
                for i, c in enumerate(cues)
            )
            + "\n"
        )
        report["assets"][name]["peak"] = float(np.max(np.abs(mixed)))
    (ROOT / "audio/manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--preflight", action="store_true")
    main(p.parse_args().preflight)
