# Product media production

Spanish-primary, source-backed product films. The application itself is unchanged.

| Export | Specifications |
| --- | --- |
| `exports/colombia-company-intelligence-promo-30s.mp4` | 30 seconds · 1920×1080 · H.264 · 30 fps |
| `exports/colombia-company-intelligence-walkthrough-60s.mp4` | 60 seconds · 1920×1080 · H.264 · 30 fps |
| `exports/colombia-company-intelligence-demo.gif` | 12 seconds · 1000×620 · infinite loop · silent |
| `exports/colombia-company-intelligence-poster.png` | 1920×1080 · static fallback |

MP4s contain Spanish neural narration, original instrumental music, burned-in captions and a selectable Spanish subtitle track. Standalone SRTs are in `captions/`. Narration and scene direction are centralized in `src/story.json`; edit that file to create future English versions. English audio/video versions are not included.

## Rebuild

Requires Python 3.12+, FFmpeg/FFprobe (libx264, AAC, loudnorm), the existing backend Playwright environment and the running app at port 5173. Composition uses Pillow rather than adding dependencies to the application. The current font is macOS Avenir Next; install a properly licensed equivalent and update `FONT` in `scripts/render.py` on another OS. Font files are not redistributed.

```sh
python3 -m venv media/.venv
media/.venv/bin/pip install -r media/requirements.txt
# requirements-lock.txt records the complete tested environment, including optional ASR.
media/.venv/bin/python media/scripts/models.py --destination /tmp/cci-media-models
# Optional: replace the recorded evidence with a new bounded application query.
# Start backend on :8000 and frontend on :5173 before recollecting.
backend/.venv/bin/python media/scripts/collect.py
backend/.venv/bin/python media/scripts/capture.py
media/.venv/bin/python media/scripts/audio.py --models /tmp/cci-media-models
media/.venv/bin/python media/scripts/render.py all
media/.venv/bin/python media/scripts/validate.py
```

Skip `collect.py` to reproduce the existing dated evidence. Browser capture replays recorded API responses with original displayed values through the real React components; it is not a live request-performance demonstration. Network access is needed for the initial voice-model download and the app's parameter catalog. No paid voice credentials are required. Models (~340 MB) and the isolated Python environment are excluded from Git. SHA-256 hashes are retained in `audio/manifest.json` and checked by `models.py`.

`render.py promo`, `render.py walkthrough`, and `render.py gif` rebuild individual exports. Motion consists of short dissolves, restrained camera pans/zooms, cursor movement and click feedback. Tall evidence scrolls through a viewport; the original full component screenshots remain in `captures/`. The loop ends on the same search state it begins on.

## Captions, sound and review

Caption cues start and finish at actual generated narration sample boundaries, one utterance per scene. They are burned into a dedicated bottom safe area and also muxed as selectable Spanish subtitles. Narration is synthesized at its native speed; scripts are shortened when a clip does not fit, rather than accelerating speech. Original music is quieter than narration and fades at both ends. FFmpeg normalizes the final mix toward −16 LUFS with a −1.5 dBTP ceiling. See `licenses/README.md`.

Lossless FLAC narration, music and mix stems are retained; intermediate WAVs are excluded from Git.

The included review PNGs are representative frames; per-scene full-resolution frames and contact sheets are in `captures/review/`. `validation.json` records codec, frame rate, exact duration, dimensions, caption boundaries, fixture arithmetic, loop and file checks. Optional local speech recognition (`pip install faster-whisper==1.2.1`, then `media/.venv/bin/python media/scripts/check_speech.py`) is an additional intelligibility check rather than proof of human listening. It downloads the public multilingual Whisper base model; audio stays local. Its transcript is retained in `audio/speech-review.json`. A native Spanish speaker should review voice delivery and pronunciation before a paid launch. Do not describe this as a human voice recording.

## Publication

The GIF is embedded near the top of the repository README. Relative MP4 links work after these files are committed. For inline social playback or release distribution, attach the MP4s to a GitHub Release and replace README links with the actual published release URLs. No release or external upload was performed. Keep the source files here even if binaries move to release hosting.

## Limits

This is a dated, reproducible product demonstration, not a claim that all sources are live or current. No synthetic company, contract or monetary value is used. RUES has a failed latest request with retained source evidence; RNVE registration is distinct from current trading. Quote screens and prices are deliberately excluded; the unfeatured quote collection is omitted from the checked-in fixture. Procurement records cover the SECOP II electronic-contract dataset, not every public procurement system. Reported contract values are neither payments nor revenue; participation is not an adverse finding. See [source attribution](SOURCES.md).
