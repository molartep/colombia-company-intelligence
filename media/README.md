# Colombia Company Intelligence — product films, revision 2

A native React / Remotion rebuild of the original screenshot compositions. Source-backed Ecopetrol records remain unchanged. The application, API, matching and financial calculations are untouched.

| Export | Specifications |
| --- | --- |
| `exports/colombia-company-intelligence-promo-30s.mp4` | 30 s · 1920×1080 · H.264 · **60 fps** · silent · Spanish captions |
| `exports/colombia-company-intelligence-walkthrough-60s.mp4` | 60 s · 1920×1080 · H.264 · **60 fps** · silent · Spanish captions |
| `exports/colombia-company-intelligence-demo.gif` | 12 s · **1000×490 · 240 frames** · 20 fps · infinite loop |
| `exports/colombia-company-intelligence-demo-loop.mp4` | Silent 60 fps loop alternative · 1920×940 |
| `exports/colombia-company-intelligence-poster.png` | 1920×1080 static fallback |

All exported and review videos are silent, with no audio tracks, as requested. The main films retain burned-in captions and a selectable Spanish subtitle track. Narration/music stems remain as archived production sources and are not muxed into exports. Scripts live in `src/story.json`; standalone `.srt` and sample-aligned cues are in `captions/`. English films were not generated.

## What changed

- **Native React, not a screenshot slideshow.** `remotion/src/Product.tsx` presents the implemented fields, source links and tabs at a readable video scale. These are condensed motion mockups of existing functionality, not a new product interface or a live screen recording. The supporting original 2× application captures remain available for comparison.
- **One company, one journey.** Search resolves to `ECOPETROL S A`, NIT `899999068-1`; the company anchor persists through identity, SFC/RNVE and SECOP. Cursor paths use smooth easing, row selection leads into the profile, the detail panel opens from the contract, and source links receive directed emphasis.
- **Purposeful choreography.** Damped springs introduce cards, a focus outline moves from NIT to registration fields, securities receive staged focus, exact metrics reveal through masks, and annual bars grow from verified aggregation data. Intermediate invented monetary values are never displayed. Scene transitions use a 650 ms fade-through-surface pattern: outgoing text clears before incoming text appears, preventing ghosted double text. Short intentional holds allow reading the values.
- **Recognizable branding.** The exact repository PNG logo appears in the opening, persistent black masthead, browser mockups, closing and GIF. Its 1254×1254 original resolution is sufficient for these placements; no invented SVG or substitute map is used.
- **Benefit-led captions.** The scripts introduce the full product name and emphasize research value. Data qualifications remain in the application and [source documentation](SOURCES.md), rather than becoming marketing headlines.
- **A purpose-built loop.** The GIF uses the same search state at both ends, full-frame global palette generation that preserves static logo colors and frame-difference checks. It has genuinely different frames, not just repeated stills. The silent MP4 preserves full 60 fps motion. Some viewers disable GIF playback; use the MP4 link in that case.

## Reproduce

Rendering requires Node 24+, FFmpeg/FFprobe, and a Chrome executable. The tested voice workflow additionally requires Apple Silicon macOS, Python 3.12 and MLX Metal. Fonts use the brand's existing installed Avenir Next / Segoe UI / sans-serif stack; font binaries are not redistributed. Other installed fonts can change line breaks, so repeat geometry and thumbnail review on another OS.

```sh
# Isolated media dependencies; no application dependencies change.
npm ci --prefix media/remotion
python3 -m venv media/.venv
media/.venv/bin/pip install -r media/requirements.txt

# Optional: prefetch the immutable Apache-2.0 voice checkpoint (~2 GB).
HF_HOME=/tmp/cci-hf media/.venv/bin/python media/scripts/models.py

# Optional archival voice generation; not required for silent video export.
HF_HOME=/tmp/cci-hf media/.venv/bin/python media/scripts/audio.py

# Render individual assets or all three; then retain captions and create the poster.
media/.venv/bin/python media/scripts/render.py all
# media/.venv/bin/python media/scripts/render.py promo
# media/.venv/bin/python media/scripts/render.py walkthrough
# media/.venv/bin/python media/scripts/render.py gif

npm run typecheck --prefix media/remotion
media/.venv/bin/python media/scripts/validate.py
```

The default Chrome executable is `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`; override it with `CCI_CHROME`. `media/remotion/package-lock.json` pins JS dependencies. `requirements-lock.txt` records the complete tested Python environment; `requirements.txt` pins the direct dependencies. Models, inference caches, `node_modules`, bundles and temporary renders are excluded from Git.

`models.py` pins the voice model to revision `5c390979e4b93af5f2932f90742ca99c7dd04687`. The original voice design description, seed and settings are retained; no reference person's voice is cloned. Accepted per-utterance inference is cached under `.cache/` for iteration. The checked-in FLAC stems preserve the earlier soundtrack for reference; all current video exports intentionally omit audio. Neural inference can vary across hardware/library versions; committed cue files are authoritative for the delivered silent films. Scripts fail if a spoken clip does not fit its window; rewrite the copy rather than accelerating speech.

To render visuals only, run `npm run render --prefix media/remotion`; `render.py --skip-render all` adds subtitles to existing silent intermediate files. A Remotion bundle may need rebuilding after changing scripts, narration cues or data. `npm run studio --prefix media/remotion` opens the composition timeline for editing.

## Review

```sh
# Regenerate full-resolution proof frames from every scene.
media/.venv/bin/python media/scripts/review.py
# Local playback with normal/half speed, seek and 50%/25% controls.
media/.venv/bin/python media/scripts/serve.py
# Open http://127.0.0.1:7332/preview.html
```

See [production audit and creative references](PRODUCTION_REVIEW.md). `captures/review-v2/` contains current scene proofs, transition strips and 50% / 25% thumbnails. Earlier captures and review frames are retained only as comparison evidence; `exports/colombia-company-intelligence-*` are the deliverables.

`validation.json` records exact durations, frames, codecs, absence of audio tracks, full decoding, caption integrity, original-logo identity, fixture reconciliation, visible motion, loop seams and hashes. All distributed MP4s are checked for zero audio tracks. Caption regions have at least 64 px bottom/side clearance; product content and captions occupy separate zones. Main names and figures remain large at thumbnail scale. Source records stay strings; exact amounts use BigInt grouping plus preserved fractional digits, without currency conversion or rounding.

The archived soundtrack was checked with speech recognition, not a human listening session. `audio/speech-review.json` retains its transcript. If audio is reintroduced in a future revision, a native Spanish speaker's audition is recommended before a paid campaign.

## Source records and scope

The dated source fixture is deliberately retained from 19 November 2026, not silently refreshed to invent current results. **Seven unique verified supplier contracts, five buyers and COP 8,137,440,199** reconcile exactly. Five registered securities are in the source fixture; the film focuses on two rows. This is an accelerated demonstration, not an upstream latency benchmark. Full provenance and limitations are in [SOURCES.md](SOURCES.md).

Only existing source-backed capabilities are shown. No prices, fraud or ownership claims, overall legitimacy verdicts, investment recommendations or comprehensive public-contract history are advertised. RNVE registration remains distinct from current trading. SECOP reported values are not payments/revenue; COP follows the application's documented policy. Participation is not an adverse finding. Public-source records retain their publishers' terms; the product logo and composition imply no publisher/company endorsement.

## Licensing and publication

See [audio / visual licenses](licenses/README.md). Original composition and sample-free music use the repository's MIT license; MLX Audio is MIT and Qwen3-TTS is Apache-2.0. Remotion has its own license, free for individuals and qualifying small teams; larger organizations must check eligibility before regenerating. It is not relicensed under this repository's MIT license.

README uses relative links to the GIF, poster and films. All exports are ordinary Git-sized files. No external release/upload was performed. When publishing a release, attach the MP4s and replace links only with actual published URLs.
