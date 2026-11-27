# Government Involvement implementation report

Implemented 2026-11-26 as an experimental foundation. Frontend and API run on localhost:5174/8000.

- Native EN/ES Government Involvement card, four independent dimensions, individual sufficiency,
  methodology dialog with Escape/focus return, secure standalone navigation and expandable trees.
- Genuine documented REST client: pinned model version, server-only API/evidence keys, batched facts,
  strict result/session validation, native decision and sufficiency evidence, bounded sizes/timeouts.
- No company transmissions or undisclosed Python inference fallback. Public demo is authored synthetic
  data with no company/run association. Real-company endpoint validates company/run scope.
- Exact calendar-month mapper, minimized session pseudonyms, isolated optional append-only evaluation
  storage/migration and synthetic CLI cache/refresh. Source evidence and matching are unchanged.
- Declarative model design, 24 explicit reference scenarios and test-only Python evaluator. A published model is configured and has passed a live synthetic evaluation; full live truth-table comparison remains pending.

Primary new files: `backend/app/integrations/rainbird/{client,mapper}.py`,
`backend/app/{schemas,services,models}/government_involvement.py`, migration `b6a7203c9101`,
`backend/tests/{test_rainbird,rainbird_reference}.py`, synthetic scenario JSON,
`frontend/src/components/GovernmentInvolvement.tsx`, types and tests,
`scripts/rae_{smoke,visual_review}.py`, `docs/RaeManual.md`, model specification and visual artifacts.
Modified: backend settings/main/Alembic registration, frontend router/Screening/styles/translations,
three existing frontend test harnesses, environment examples, README, capabilities, architecture,
SECOP methodology, localization, brand manual and validation notes.

Recent example chain: documented → verified supplier → signature 2026-05-14 within
2024-11-26…2026-11-26 → synthetic observation. It is not a captured native Rae tree.

Validation: 311 backend tests pass / 66 skip; 154 frontend tests pass; Ruff, mypy, ESLint, TypeScript,
Prettier, production frontend build and local migration/schema check pass. Responsive visual inspection
covers both languages at 390/768/1440px. See [screenshots](../design/assets/rainbird/README.md).
The initial Vite bundle warning was resolved in a follow-up with lazy routes and a cacheable shared runtime; see the validation notes. No live inference timings or Rae/reference agreement were measured.

Activation: follow [manual sections 5, 8 and 16](../RaeManual.md), create and test the model in Studio,
configure private backend credentials and published integer version, explicitly enable experimental
mode, then invoke `backend/.venv/bin/python scripts/rae_smoke.py`. Only the fixed synthetic fixture
can be sent. Company processing remains blocked.

Remaining: validated executable native map/export, full live truth-table and evidence comparison,
commercial licensing/data processing/retention review and separate company-data authorization;
field-specific contradiction evidence (current SECOP excludes whole conflicting versions); production
failure/cache lifecycle and richer native provenance navigation. No production-ready claim is made.

**Recommendation: Defer.** The reference rules are small and operationally simpler. Rae's potential
explainability and policy-maintenance value needs a genuine published-model comparison before adoption.

Backend wheel build also passed. A local database-backed read-only company endpoint smoke check
confirmed disabled mode with no findings and rejection of an invalid run ID. Full PostgreSQL test-suite
execution still requires a dedicated disposable TEST_DATABASE_URL and was not performed.


Company reasoning update: authorized live mode now includes verified snapshot mapping, native witness
source resolution, persistent cache/failure history, concurrency/cooldown controls and explicit refresh.
The card joins the three visualizations in a responsive 2×2 grid. A real synthetic call passed in
4.689 seconds. Real-company execution was rejected by automatic approval review; local activation
awaits the specific payload/destination approval, with no real-company facts transmitted.


Activation completed after explicit approval: ongoing minimized company facts may be sent to the
configured Enterprise Rae API. Local live mode is enabled. A two-contract real company snapshot
completed in 5.918 seconds with native evidence, per-decision source references and cached reuse.
Direct/historical/recent participation were documented; execution remained undetermined because the
source snapshot was stale. Full live scenario coverage and production operations remain separate work.
