"""Validate source arithmetic, exact export specs, captions, audio absence and visible motion."""

import hashlib
import json
import subprocess
from decimal import Decimal
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "exports"
report = {}


def probe(p):
    return json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(p),
            ]
        )
    )


def motion(p):
    data = subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(p),
            "-vf",
            "fps=10,scale=192:108:flags=area,format=gray",
            "-f",
            "rawvideo",
            "-",
        ]
    )
    frames = np.frombuffer(data, np.uint8).reshape((-1, 108, 192)).astype(np.float32)
    delta = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2))
    longest = run = 0
    for x in delta:
        run = run + 1 if x < 0.02 else 0
        longest = max(longest, run)
    assert int(np.count_nonzero(delta > 0.06)) > 20, (
        "Export has insufficient visible motion"
    )
    assert longest / 10 < 7, "Unexpected extended freeze"
    return {
        "samples": len(frames),
        "moving_sample_intervals": int(np.count_nonzero(delta > 0.06)),
        "largest_mean_frame_difference": round(float(delta.max()), 3),
        "longest_near_static_read_hold_seconds": longest / 10,
    }


d = json.loads((ROOT / "fixtures/ecopetrol.json").read_text())
rows = d["contracts"]["items"] + d["contracts_page2"]["items"]
summary = d["secop"]["summary"]
assert d["profile"]["nit"] == "899999068" and d["profile"]["verification_digit"] == "1"
assert (
    len(rows)
    == len({r["contract_id"] for r in rows})
    == summary["total_contracts"]
    == 7
)
assert all(
    r["match_status"] == "verified"
    and r["normalized_supplier_identifier"] == "899999068"
    and r["currency"] == "COP"
    for r in rows
)
total = sum((Decimal(r["value"]) for r in rows if r["value"] is not None), Decimal(0))
assert total == Decimal(summary["total_values"]["COP"]) == Decimal(8137440199)
assert sum(Decimal(r["values"]["COP"]) for r in summary["annual"]) == total
assert summary["distinct_buyers"] == len({r["buyer"] for r in rows}) == 5
assert summary["latest_signature_date"] == max(
    r["signature_date"] for r in rows if r["signature_date"]
)
assert d["detail"]["contract_id"] == "CO1.PCCNTR.8317598" and d["detail"][
    "contract_id"
] in {r["contract_id"] for r in rows}
assert (
    d["markets"]["rnve"]["match_status"] == "verified"
    and d["securities"]["unfiltered_total"] == 5
)
assert (ROOT.parent / "frontend/public/colombia-network-logo.png").read_bytes() == (
    ROOT / "remotion/public/colombia-network-logo.png"
).read_bytes()
report["evidence"] = {
    "nit": d["profile"]["nit"],
    "unique_contracts": len(rows),
    "reconciled_cop": str(total),
    "distinct_buyers": 5,
    "registered_securities": 5,
    "logo_matches_original": True,
}
story = json.loads((ROOT / "src/story.json").read_text())
for name, seconds in [("promo", 30), ("walkthrough", 60)]:
    p = OUT / f"colombia-company-intelligence-{name}-{seconds}s.mp4"
    info = probe(p)
    v = next(x for x in info["streams"] if x["codec_type"] == "video")
    assert not any(x["codec_type"] == "audio" for x in info["streams"])
    s = next(x for x in info["streams"] if x["codec_type"] == "subtitle")
    assert (
        v["width"],
        v["height"],
        v["codec_name"],
        v["avg_frame_rate"],
        v["pix_fmt"],
    ) == (1920, 1080, "h264", "60/1", "yuv420p")
    assert (
        int(v["nb_frames"]) == seconds * 60
        and abs(float(info["format"]["duration"]) - seconds) < 0.05
    )
    assert s["tags"]["language"] == "spa"
    cues = json.loads((ROOT / f"captions/{name}.json").read_text())
    last = 0
    assert len(cues) == len(story[name]["narration"])
    for c, original in zip(cues, story[name]["narration"]):
        assert (
            last <= c["start"] < c["end"] <= seconds and c["text"] == original["text"]
        )
        last = c["end"]
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(p), "-f", "null", "-"], check=True
    )
    report[name] = {
        "duration": info["format"]["duration"],
        "video": {
            k: v[k]
            for k in ["codec_name", "width", "height", "avg_frame_rate", "nb_frames"]
        },
        "audio_tracks": 0,
        "captions": len(cues),
        "bytes": p.stat().st_size,
        "fully_decoded": True,
        "motion": motion(p),
    }
p = OUT / "colombia-company-intelligence-demo.gif"
im = Image.open(p)
assert im.size == (1000, 490) and im.info["loop"] == 0 and im.n_frames >= 200
first = im.convert("RGB")
duration = 0
different = 0
prev = first
# Palette generation must preserve the static official logo, not turn it gray.
logo = np.array(first.crop((40, 4, 88, 55))).astype(float)
r, g, b = logo[:, :, 0], logo[:, :, 1], logo[:, :, 2]
colors = {
    "yellow": int(((r > 130) & (g > 100) & (b < 120) & (r > b * 1.4)).sum()),
    "blue": int(((b > r * 1.25) & (b > g * 1.05) & (b > 80)).sum()),
    "red": int(((r > g * 1.4) & (r > b * 1.15) & (r > 100)).sum()),
}
assert all(n > 6 for n in colors.values()), "GIF palette lost official brand colors"

for i in range(im.n_frames):
    im.seek(i)
    duration += im.info.get("duration", 0)
    f = im.convert("RGB")
    different += sum(ImageStat.Stat(ImageChops.difference(prev, f)).mean) > 0.05
    prev = f
assert 11900 <= duration <= 12100 and different > 70
mean = sum(ImageStat.Stat(ImageChops.difference(first, im.convert("RGB"))).mean) / 3
assert mean < 1
report["gif"] = {
    "size": list(im.size),
    "frames": im.n_frames,
    "duration_ms": duration,
    "loop": 0,
    "bytes": p.stat().st_size,
    "visibly_changed_frames": different,
    "first_last_mean_difference": round(mean, 3),
    "logo_color_pixels": colors,
}
loop = probe(OUT / "colombia-company-intelligence-demo-loop.mp4")
assert not any(s["codec_type"] == "audio" for s in loop["streams"])
report["silent_loop"] = {
    "duration": loop["format"]["duration"],
    "motion": motion(OUT / "colombia-company-intelligence-demo-loop.mp4"),
}
# Include all distributed video files, including review clips.
report["silent_videos"] = []
for video in sorted(ROOT.rglob("*.mp4")):
    if any(
        part in {"node_modules", ".venv", ".cache", ".work", "build"}
        for part in video.parts
    ):
        continue
    assert not any(x["codec_type"] == "audio" for x in probe(video)["streams"]), video
    report["silent_videos"].append(str(video.relative_to(ROOT)))
poster = Image.open(OUT / "colombia-company-intelligence-poster.png")
assert poster.size == (1920, 1080)
report["poster"] = {"size": list(poster.size)}
report["sha256"] = {
    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
    for p in OUT.iterdir()
    if p.suffix in [".mp4", ".gif", ".png"]
}
(ROOT / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
