"""Rebuild silent V2 Remotion exports, retain captions, and create loop media."""

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "exports"
WORK = OUT / ".work"
WORK.mkdir(exist_ok=True)
PREFIX = "colombia-company-intelligence-"


def run(args):
    subprocess.run(args, check=True)


def main(asset, skip_render=False):
    names = ["promo", "walkthrough", "gif"] if asset == "all" else [asset]
    for name in names:
        if not skip_render:
            subprocess.run(
                ["node", "render.mjs", name], cwd=ROOT / "remotion", check=True
            )
        source = WORK / f"{name}-silent.mp4"
        if name == "gif":
            run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    str(source),
                    "-filter_complex",
                    "[0:v]fps=20,crop=1920:940:0:0,scale=1000:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=256:stats_mode=full:reserve_transparent=0[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
                    "-loop",
                    "0",
                    str(OUT / (PREFIX + "demo.gif")),
                ]
            )
            run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    str(source),
                    "-vf",
                    "crop=1920:940:0:0",
                    "-c:v",
                    "libx264",
                    "-crf",
                    "18",
                    "-preset",
                    "fast",
                    "-pix_fmt",
                    "yuv420p",
                    "-an",
                    "-movflags",
                    "+faststart",
                    str(OUT / (PREFIX + "demo-loop.mp4")),
                ]
            )
        else:
            seconds = 30 if name == "promo" else 60
            run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    str(source),
                    "-i",
                    str(ROOT / f"captions/{name}.srt"),
                    "-map",
                    "0:v",
                    "-map",
                    "1:s",
                    "-c:v",
                    "copy",
                    "-an",
                    "-c:s",
                    "mov_text",
                    "-metadata:s:s:0",
                    "language=spa",
                    "-movflags",
                    "+faststart",
                    "-t",
                    str(seconds),
                    str(OUT / (PREFIX + f"{name}-{seconds}s.mp4")),
                ]
            )
    if "promo" in names:
        run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-ss",
                "2.65",
                "-i",
                str(OUT / (PREFIX + "promo-30s.mp4")),
                "-frames:v",
                "1",
                str(OUT / (PREFIX + "poster.png")),
            ]
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "asset",
        choices=["promo", "walkthrough", "gif", "all"],
        default="all",
        nargs="?",
    )
    p.add_argument("--skip-render", action="store_true")
    a = p.parse_args()
    main(a.asset, a.skip_render)
