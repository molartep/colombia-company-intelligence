# RUES timeout and cache warnings — 2026-11-24

With Vite running on port 5174, reproduce the synthetic checks from the repository root:

```sh
backend/.venv/bin/python scripts/rues_timeout_review.py --base-url http://127.0.0.1:5174
```

The harness intercepts only search API requests. No upstream requests or real company records are
used. EN/ES checks at 320, 390, 768 and 1440px verify explicit RUES attribution, human-readable
messages without raw error codes, and no page-level overflow. Existing warning/error components
and refresh actions are reused; no visual tokens or layout contracts change.

| State | Desktop EN | Mobile ES |
| --- | --- | --- |
| Timeout with cached matches, explicitly stale/incomplete | [1440px](cached-en-1440.png) | [390px](cached-es-390.png) |
| Timeout without matching cache, explicit error | [1440px](no-cache-en-1440.png) | [390px](no-cache-es-390.png) |

`inspection.json` records all 16 language/width/state outcomes. Images use synthetic evidence,
including the company shown in the cached table. The typed query reproduces the reported user flow.
