"""Extract actual encoded scenes, thumbnail tests and slow transition evidence."""

import json
import subprocess
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "captures/review-v2"
OUT.mkdir(exist_ok=True)
TEMP = ROOT / "exports/.work"
TEMP.mkdir(exist_ok=True)
story = json.loads((ROOT / "src/story.json").read_text())


def extract(video, t, path):
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-ss",
            str(t),
            "-i",
            str(video),
            "-frames:v",
            "1",
            str(path),
        ],
        check=True,
    )


for name, seconds in [("promo", 30), ("walkthrough", 60)]:
    video = ROOT / f"exports/colombia-company-intelligence-{name}-{seconds}s.mp4"
    tiles = []
    for i, s in enumerate(story[name]["scenes"]):
        t = (s["start"] + s["end"]) / 2
        p = OUT / f"{name}-scene-{i:02}.png"
        extract(video, t, p)
        im = Image.open(p)
        for scale, label in [(0.5, "50pct"), (0.25, "25pct")]:
            im.resize(
                (round(im.width * scale), round(im.height * scale)),
                Image.Resampling.LANCZOS,
            ).save(OUT / f"{name}-scene-{i:02}-{label}.png")
        tiles.append(im.resize((480, 270), Image.Resampling.LANCZOS))
    sheet = Image.new("RGB", (1440, ((len(tiles) + 2) // 3) * 270), "white")
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % 3) * 480, (i // 3) * 270))
    sheet.save(OUT / f"{name}-contact-sheet.png")
    for i, s in enumerate(story[name]["scenes"][1:]):
        strip = Image.new("RGB", (1920, 216), "white")
        for j, offset in enumerate([-0.25, 0, 0.25, 0.5, 0.85]):
            p = TEMP / "transition-frame.png"
            extract(video, max(0, s["start"] + offset), p)
            im = Image.open(p).resize((384, 216), Image.Resampling.LANCZOS)
            strip.paste(im, (384 * j, 0))
        strip.save(OUT / f"{name}-transition-{i:02}.png")
    # Slow-motion review file: first ten seconds at half speed, no audio pitch changes.
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-t",
            "10",
            "-i",
            str(video),
            "-an",
            "-vf",
            "setpts=2*PTS,scale=960:-1:flags=lanczos",
            "-r",
            "60",
            "-c:v",
            "libx264",
            "-crf",
            "20",
            "-movflags",
            "+faststart",
            str(OUT / f"{name}-half-speed-review.mp4"),
        ],
        check=True,
    )
old = Path("/tmp/cci-media-before/promo-frame.png")
if old.exists():
    new = OUT / "promo-scene-03.png"
    pair = Image.new("RGB", (1920, 540), "white")
    pair.paste(Image.open(old).resize((960, 540), Image.Resampling.LANCZOS), (0, 0))
    pair.paste(Image.open(new).resize((960, 540), Image.Resampling.LANCZOS), (960, 0))
    pair.save(OUT / "before-after-contracts.png")
print(
    "Extracted encoded scenes, 50%/25% thumbnails, transition strips and half-speed reviews."
)

# GIF proofs come from the actual animated file, not a static poster.
gif = Image.open(ROOT / "exports/colombia-company-intelligence-demo.gif")
for i, scene in enumerate(story["gif"]["scenes"]):
    gif.seek(min(gif.n_frames - 1, round((scene["start"] + scene["end"]) / 2 * 20)))
    gif.convert("RGB").save(OUT / f"gif-scene-{i:02}.png")
