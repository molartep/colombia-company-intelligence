# Currency, exports and capability review — 2026-11-24

Run Vite (`cd frontend && npm run dev -- --port 5174`), then from the repository root:

```sh
backend/.venv/bin/python scripts/research_presentation_review.py --base-url http://127.0.0.1:5174
```

Uses existing synthetic `ui-review.json` fixtures; no company research or supplier calls leave the
machine. Playwright checks EN/ES at 320, 390, 768 and 1440px, reduced motion, visible focus outlines,
USD replacing COP, dynamic currency labels, the single-line export bar above the title, CSV/JSON dropdown dismissal,
reference failure preserving COP, viewport-contained
information tooltips with Escape dismissal, and no page-level overflow. Table content
scrolls locally. `inspection.json` records outcomes. Representative captures retained:

| State | Desktop EN | Mobile ES |
| --- | --- | --- |
| Custom Currency options | [1440px](dropdown-currency-en-1440.png) | [390px](dropdown-currency-es-390.png) |
| Custom export scope options | [1440px](dropdown-scope-en-1440.png) | [390px](dropdown-scope-es-390.png) |
| Custom Government Contracts options | [1440px](dropdown-contracts-en-1440.png) | [390px](dropdown-contracts-es-390.png) |
| Custom Capital Markets options | [1440px](dropdown-markets-en-1440.png) | [390px](dropdown-markets-es-390.png) |
| Custom advanced-search options | [1440px](dropdown-advanced-en-1440.png) | [390px](dropdown-advanced-es-390.png) |
| Single top export bar, CSV/JSON dropdown | [1440px](export-en-1440.png) | [390px](export-es-390.png) |
| Top-right Currency card, manual USD replacement, export controls | [1440px](manual-en-1440.png) | [390px](manual-es-390.png) |
| Reference provider unavailable, original COP retained | [1440px](unavailable-en-1440.png) | [390px](unavailable-es-390.png) |
| References capability matrix | [1440px](references-en-1440.png) | [390px](references-es-390.png) |

Browser tests use synthetic provider failure; a separate one-row live TRM adapter check succeeded
on 2026-11-24 with COP-per-USD `3505.92`, effective 2026-11-24, no stale/failure flags. This observation
does not guarantee future provider availability. Formal screen-reader certification is not claimed.

The simplified card supersedes the earlier collapsed currency disclosure. Original amounts remain
in storage and exports; selecting COP restores them on screen. USD uses the same element and
typography with an ≈ prefix. The manual-entry date input has been removed.

All selection controls now use shared custom dropdowns matching Export. The harness checks that
profile, Capital Markets and advanced-search views contain no native selects/datalists and verifies
portal popup bounds at every supported width. Keyboard/raw-value behavior is covered by unit tests.
