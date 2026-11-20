# Production review — revision 2

**Current delivery:** audio was removed from every video at the user’s request. The original narration/music work below is historical; current exports retain Spanish captions only.

## Audit of the previous films

The previous deliverables were inspected through their source, actual encoded frames, application captures and GIF decoding. The local original GIF contained 180 frames; that alone did not establish that its motion was effective or that a README viewer would play it. Revision 2 checks actual visible differences and browser playback as well as frame count.

| Area | Previous issue | Revision 2 response |
| --- | --- | --- |
| Opening | Delayed the benefit behind a disconnected-sources explanation. | Lead with the complete product name and research value; search resolves into the same verified Ecopetrol identity. |
| Framing | Whole dense screenshots shrank important labels and financial figures. | Native React presentation of selected fields; two securities rows; exact large contract metrics; bounded contract detail. |
| Hierarchy | Portrait panels occupied a narrow portion of a wide empty canvas. | Full-width focused product windows, balanced hero split and a connected three-source summary. |
| Brand | Logo was mainly a closing decoration. | Exact original logo in every persistent masthead, early reveal, browser frame, closing and GIF. |
| Motion | Generic screenshot movement and short dissolves did little to explain a task. | Frame-accurate springs, intentional cursor paths, NIT/field focus, securities emphasis, exact-value reveal masks, growing verified bars and a contract drawer. |
| Narration | Some foreign-name pronunciation was weak; cautionary wording dominated feature headlines. | A new Spanish-specific designed voice, benefit-led copy and a verified pronunciation transcript; qualifications remain in source documentation. |
| GIF | Existence/frame count was treated as sufficient; visibility and palette were under-tested. | Dedicated 240-frame loop, actual browser playback, changed-frame counts, seam comparison and a silent 60 fps MP4 alternative. |

## Creative references

No reference footage, music, typography, logos or graphics were reused. The following references informed principles rather than a borrowed visual identity:

| Reference | What was actually inspected | Principle applied |
| --- | --- | --- |
| [Linear Plan](https://linear.app/plan) | Page hierarchy and product presentation. | One clear benefit and focal subject; quieter supporting metadata. |
| [Linear: Building with your users](https://linear.app/learn/building-with-your-users) | The embedded video was played; product and integration views were inspected at approximately 33 and 58 seconds, alongside its workflow outline. | Keep the same research subject and preserve context as the user moves between source views. |
| [Loom product demo](https://www.loom.com/community/product-demo) | Embedded player, transcript and end state. A full uninterrupted visual review was not recorded. | Explain a concrete user goal with concise spoken actions, rather than reciting interface labels. |
| [Remotion showcase](https://www.remotion.dev/showcase) | Current showcase catalog and product/statistics use cases; not every linked film. | Use native timeline components for readable metrics and controlled motion. |
| [Raycast: New Raycast, Coming 2026](https://www.youtube.com/watch?v=Mi173xGb0ZA) | Actual playing product footage, including the enlarged file/result view around 10 seconds, reached from the [official Raycast launch article](https://www.raycast.com/blog/the-new-raycast). | Let a selected result dominate the frame; use crisp, deliberate product movement. |
| [Stripe Sessions product keynote](https://stripe.com/gb/sessions/2025/product-keynote) | Official keynote page and the linked public video listing; a complete keynote/motion review was not performed. | Used only as broad brand/presentation context; no specific unobserved animation is claimed as a reference. |

## Composition contract

- 1920×1080, 60 fps video; minimum 80 px side content margin and 64 px caption bottom margin.
- Existing black, dark teal, green, white and neutral palette; installed Avenir Next / existing font fallbacks.
- Main headlines 64–82 px; company identity 58 px; NIT 49 px; exact KPIs 76–78 px; essential securities 38 px; supporting labels generally 24–32 px; captions 34 px.
- The browser focuses on existing fields/controls at video scale. It is a condensed motion mockup, not a redesigned live application or an upstream performance measurement.
- The company NIT stays unchanged; no name-based group attribution. Source names/security names stay original. Approved SECOP uppercase treatment matches the application.
- Amounts retain every digit on one line. Currency is in section/card titles. No counter-up animation invents intermediate contract amounts.
- A 650 ms **fade-through-surface** clears outgoing text before incoming text appears; source/brand anchors persist. This replaces ghosting from overlapping full-scene dissolves.
- GIF palette generation uses the whole frame and all 256 colors so the unchanging official logo retains yellow, blue and red. Difference-only palette statistics were rejected after they muted the static logo.
- No prices, unsupported ownership claims, risk scores or claims of comprehensive government-contract coverage are included.

## Validation and evidence

`validation.json` is generated from the actual exported files. It verifies 1,800 / 3,600 video frames, durations, codecs, zero audio tracks, subtitles, complete decoding, source arithmetic, visible motion and the loop seam. It independently verifies the original logo bytes and supplier association. The missing-signature-date value bucket remains in annual totals.

`captures/review-v2/` contains actual encoded scene frames, **50% and 25%** thumbnails, transition strips, contact sheets, half-speed review clips, and a before/after comparison. Main headings, company identity and highlighted contract values are assessed at thumbnail size; metadata is supporting information rather than a requirement to read an entire source table in a thumbnail.

Normal and half-speed playback are inspected through `preview.html` and the loopback Range server; raw GIF playback is checked in a browser. Palette fidelity and doubled transition text were caught during this review and corrected before delivery. Automated motion sampling supplements the visual checks; short purposeful holds allow reading the original values and closing URL.

The narration was regenerated after testing alternatives. A candidate with extended pauses and a garbled introduction was rejected. The accepted generic Spanish-specific voice is not cloned from a person; scripts are shortened/re-timed instead of accelerating speech. The accepted transcript is in `audio/speech-review.json`. Machine transcription does not establish human-listening approval; a native-speaker audition is still recommended before paid distribution.

## Scope and known limits

- Source fixture: dated 19 November 2026. Seven supplier contracts, five buyers, COP 8,137,440,199; five registered securities, of which two are featured. The application has retained evidence despite a failed latest RUES retrieval; this is not portrayed as a fresh live check.
- Necessary source/financial qualifications are preserved in the application and [SOURCES.md](SOURCES.md), rather than elevated into launch headlines.
- GIF playback can be paused by a viewer/browser/accessibility setting. The file is genuinely animated; the silent MP4 is available as an alternative.
- The production environment uses Apple Silicon, MLX and installed system fonts. Other fonts/platforms require a fresh layout/voice review.
- English variants and external publication are outside this delivered revision. Source composition, scripts, accepted audio stems, captions and licenses remain reproducible.

## Final verification results · 20 November 2026

| Asset | Observed result |
| --- | --- |
| Promo | 30.000 s; 1920×1080; H.264 60 fps; 1800 frames; no audio tracks; 5 Spanish cues; complete decode passed. |
| Walkthrough | 60.000 s; 1920×1080; H.264 60 fps; 3600 frames; no audio tracks; 8 Spanish cues; complete decode passed. |
| GIF | 240 frames; 12 s; 1000×490; infinite loop; 2.84 MB; 161 visibly changed frames; mean seam difference 0.123/255; yellow/blue/red logo pixels verified. |

Frontend lint, type checking, 128 tests and production build passed (the existing bundle-size advisory remains). The media TypeScript check, three evidence/precision tests, Python Ruff checks, source reconciliation and export validation passed. No new application feature, API or database migration was introduced.
