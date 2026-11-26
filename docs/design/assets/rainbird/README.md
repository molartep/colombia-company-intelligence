# Government Involvement visual review

2026-11-26 · synthetic profiles and explicitly authored synthetic reasoning examples only.
No real company data or Rae inference was used for these images.

Reproduce with Vite on 5174:

```sh
backend/.venv/bin/python scripts/rae_visual_review.py
```

Both EN/ES at 390, 768 and 1440px; reduced motion; no page-level overflow or browser errors;
native dialog Escape/focus return and secure new-tab link. `inspection.json` records each run.

| View | English desktop | Spanish mobile |
| --- | --- | --- |
| Government Contracts card | [1440px](card-en-1440.png) | [390px](card-es-390.png) |
| Learn more dialog | [1440px](dialog-en-1440.png) | [390px](dialog-es-390.png) |
| Expanded recent evidence | [1440px](evidence-en-1440.png) | [390px](evidence-es-390.png) |
| Standalone methodology | [1440px](methodology-en-1440.png) | [390px](methodology-es-390.png) |

Equivalent 768px and other language/width combinations are stored alongside these files.
Full-page profile captures retain existing contract tables with local horizontal scrolling.
These are actual Chromium captures, not generated mockups. Native Rae evidence remains unverified.
