# Executed validation — 2026-11-13

Environment: macOS arm64, Python 3.12.15, Node 24.3.0. This machine has no Docker or PostgreSQL CLI
installation. A temporary `pgserver` runtime supplied **real PostgreSQL 16.2** using a private temporary
Unix socket; it is a local validation aid, not an application dependency or a committed database.

## Passed

- Live source metadata discovery: 36 text columns; official update timestamps saved in
  `docs/discovery/metadata.json`. Representative records and filtered SODA 2.x queries inspected;
  no personal raw records committed.
- `make smoke`: actual adapter metadata validation plus one bounded exact-NIT and one bounded name
  request; both returned valid official records with source row IDs.
- **126 backend tests passed**, including real PostgreSQL persistence, separate registration IDs,
  payload-version deduplication, foreign-key relationships, pagination, API profile/source routes,
  public-field filtering, cached normalized-name matching, source failure behavior, and migration
  upgrade → downgrade → re-upgrade → Alembic model-drift check.
- **43 frontend tests passed**: submit-only search, animated retrieval-dialog lifecycle, result/profile link rendering, NIT column separation, registration-status colors, source-error
  states, empty results, and company profile/unchecked attribute rendering.
- Ruff lint and format checks; strict mypy on `app`; ESLint and strict TypeScript.
- Vite production bundle; Python backend wheel packaging.
- npm audit after updating test/lint dependencies: **zero known vulnerabilities**. A scoped minimatch
  override supplies a patched release to TypeScript ESLint's parser dependency; lint/build tests pass.
- Full unmocked API workflow against a separate temporary PostgreSQL database and official RUES:
  liveness/readiness/source catalogue, fresh exact-NIT search, persisted profile, allowlisted source
  records, and fresh filtered-name search. The final fresh-name check used `SOCRATA_TIMEOUT=45`
  and one retry; both search responses were explicitly asserted non-stale.
- Actual browser UI: official NIT search, result → registration profile, copy-NIT success feedback,
  Sources section, official links, unavailable geography, separate freshness timestamps, and coming-later
  sections. Home layout visually inspected at the default viewport and a 390×844 mobile viewport.
- `git diff --check`.

## Limits and observations

- During the initial validation, government requests intermittently timed out. The then-20-second
  default could trigger stale fallback;
  longer configurable timeouts helped during validation. No latency/service-availability guarantee
  is made. The browser showed the separately persisted failed-to-retrieve source status during an
  intermittent outage, while cached profiles remained available.
- Docker images/Compose startup were **not executed locally**, because Docker is unavailable here.
  GitHub Actions run 43532494802 successfully built the images and passed backend/database readiness,
  but its immediate frontend curl raced Vite startup and failed with a connection reset. The
  subsequent health-check/wait fix has not yet been executed with Docker locally or on GitHub.
- Production deployment, authentication, automated retention, broad natural-person privacy review,
  exhaustive registry-wide matching, and browser automation coverage beyond the manual checks above
  are not claimed. This is a local Phase 1 foundation.
- Type checking, builds, and standard tests are reproducible with the commands below. Full database
  tests need a disposable PostgreSQL database and never contact the government service.

```sh
make install
make lint
make test
make test-db
make build
make smoke                       # Explicit optional network check
# Docker validation when available:
cp .env.example .env
docker compose config --quiet
docker compose up --build --wait --wait-timeout 120
curl --fail http://127.0.0.1:8000/ready
curl --fail http://127.0.0.1:5173
```


Spacing-search regression validation adds compact/spaced query equivalence, escaped literals,
space-insensitive match classification, preservation of legal suffixes and separate identities,
pagination, cached matches during empty responses/outages, and previous-name alias recovery.
The full 66-test backend suite passed against PostgreSQL, including the additional expression-index
migration, downgrade/re-upgrade, and Alembic model-drift check.


## Compose startup race correction

Inspected the compose job logs for run 43532494802: the frontend container was marked started at
00:12:34.8139913 UTC and curl failed at 00:12:34.8404266 UTC, before any frontend startup output.
The backend and frontend CI jobs passed independently. This is a readiness race: detached container
startup did not wait for Vite's HTTP listener, and the frontend probe had no retries.

The frontend now has a Node-native HTTP health check (3-second request timeout, non-2xx/network
failures mark unhealthy). CI and `make up` use Compose `--wait --wait-timeout 120`; successful
completion of the migration service remains a required dependency. Both published-port probes use
bounded curl retries including connection resets/refusals. Status/log collection and cleanup are
separate always-run steps, so diagnostic failure cannot prevent cleanup.


Local verification for this correction: Compose/workflow YAML parsed successfully, and the exact
frontend health command passed against the running Vite server. A temporary HTTP server verified
that the health command fails for HTTP 503 and connection resets; the exact CI frontend curl command
recovered from an initial reset on its second attempt and still failed after four attempts for a
persistent reset. These checks exercised real HTTP sockets and the actual configured commands;
they do not substitute for executing Docker Compose on the next CI run.


Registration-profile presentation checks cover shared status colors, a missing NIT with a stray
verification digit, red missing-field pills, green present attributes, source availability dots,
calendar-date formatting, leap years, impossible dates, zero/year-9999 date placeholders, and
1900-01-01 RUES timestamps in different offset forms. All 23 frontend tests, ESLint, strict TypeScript,
and the production build passed. The existing cached registration profile was also checked in the
browser in Overview and Sources; raw source values and backend records remain unchanged.


Profile-navigation checks cover both result links (legal name and arrow), preserving query/page
through Sources and Overview, restoring an already-stale cached search without a network request,
and explicitly submitting a cached search to fetch fresh results. All 25 frontend tests, ESLint,
strict TypeScript, and the production build passed. The header status now occupies a separate
labeled line beneath NIT, the RUES seal card is removed, and source-record field disclosures have
additional separation from the preceding metadata.


Search-date columns are supplied by the existing latest-source-record query, without additional
upstream calls. Backend regression coverage confirms dates come from the latest version and that
missing/empty values remain null, including cached fallback; older dates and renewal years are not
substituted. Frontend coverage checks both formatted date columns, truly empty cells for missing
NIT/dates, and a red missing-NIT pill in the profile. All 67 backend and 25 frontend tests passed.


Home branding checks confirm the old headline/description are removed, the custom transparent
Colombia network logo is used, and accessible GitHub/LinkedIn icon links point to the requested
personal profiles with safe new-tab behavior. All 26 frontend tests, ESLint, strict TypeScript,
and the production build passed. The image asset and its exact generation prompt are tracked in
`docs/branding.md` and `frontend/public/colombia-network-logo.png`.


## Global source relevance ordering

The full **70-test backend suite** passed against real PostgreSQL. A source simulation executes the
actual generated filtering, relevance expression, tie-breakers, and pagination in SQL. It confirms
that strong matches with late source row IDs precede 24 weaker early rows, API pagination preserves
that order without duplicates, verification-digit matches come first, and cached outage fallback
reports page-local ranking. All **26 frontend tests**, Ruff, strict mypy, ESLint, strict TypeScript,
and the Vite production build passed.

Live RUES accepted the computed CASE ordering with `unaccent`, `upper`, `trim`, and literal
`replace`; `regex_replace` was rejected and is not used. The optional
`SOCRATA_TIMEOUT=45 backend/.venv/bin/python scripts/live_smoke.py --ranking` passed metadata,
exact-NIT, name, and ranked page-boundary checks. Two five-row Zulu pages exactly matched one
ten-row query by source row ID. This is a bounded live check, not an exhaustive search-quality
benchmark or a snapshot/latency guarantee. Candidate filtering remains case/space-insensitive;
typo tolerance and broader accent/punctuation retrieval are not added.

The restarted local API also returned a fresh, non-stale `olartemoure` search with
`OLARTE MOURE & ASOCIADOS SAS` before `FUNDACIÓN OLARTE MOURE`, reporting
`ranking_scope: all matching source records`.


## Advanced source filters and parameter catalog — 2026-11-14

- **92 backend tests passed** against real PostgreSQL, including migrations, filter validation,
  generated source WHERE execution before pagination, cache/source calendar parity, century/leap
  dates, zero/malformed/year-9999 placeholders, latest-record filter predicates, filtered lookahead,
  stale outage/empty-source fallback, no matching filtered cache, and public provenance privacy.
- **31 frontend tests passed**, including all seven filters, source-code multi-selection, submit-only
  behavior, reset to page 1, filter preservation through Next and profile-return caching, clear
  behavior, keyboard-help associations, Parameters code meanings, and canonical cache keys.
- Ruff lint/format, strict mypy, ESLint, strict TypeScript, frontend production bundle, and backend
  wheel build passed. The wheel was inspected for the bundled JSON parameter catalog.
- Four bounded live GROUP BY queries discovered 15 status options (including missing), 58 chambers,
  53 legal organizations, and 2 registration categories. No company/person data or counts are
  stored in the catalog. The actual documented refresh script passed metadata plus all four
  bounded aggregations with `SOCRATA_TIMEOUT=60`.
- Live RUES accepted combined code/registration/renewal ranges, primary exact CIIU, any-activity
  prefix CIIU, and exact/minimum renewed-year queries. The full local FastAPI request returned a
  fresh, non-stale filtered Palomma result with valid source dates and global ranking scope.
- Isolated real Chrome checks verified all four option groups, no company request when expanding
  filters, visible keyboard-focus help, Parameters rendering, and no horizontal page overflow at
  390px. Desktop and mobile screenshots were inspected. The in-app browser control was unavailable;
  the isolated browser used the same local frontend/backend.

The fixed catalog is a versioned snapshot of observed code/label pairs, not a separately certified
legal taxonomy or a live facet-count service. Newly published codes require explicit refresh and
review. Standard tests remain fully independent of government services; only the optional refresh
and live checks contact RUES. Docker remains unavailable locally and was not executed for this change.


## Phase 2 capital-markets validation — 2026-11-14

Baseline before changes: **92 backend tests** against real PostgreSQL and **37 frontend tests**,
plus frontend lint/type/build, passed. Final **126 backend tests** and **43 frontend tests** passed.
The final backend run had no warnings. Ruff lint/format, strict mypy (38 source files), ESLint,
strict TypeScript, Vite production build and backend wheel packaging passed.

Database validation includes migration head → base → head, model-drift checks, and an explicit
downgrade to the Phase 1 revision followed by upgrade with existing RUES data preserved. Phase 2
tests exercise idempotence, immutable source history, transactional rollback after a partial upsert,
failed-refresh preservation, shared-NIT ambiguity, name-only/historical-name candidates, NIT priority
over unrelated same-name entities, rejected-link safeguards, status history, stale/incomplete negative
guards, securities pagination/filtering and privacy-safe provenance. Fixtures are synthetic.

Live source checks actually executed:

- Official SFC public issuer Excel export downloaded through its visible report button; **311 rows**
  parsed, matching the unfiltered directory count. All 141 ordinary-corporate identifiers passed
  the opt-in DV rule; 170 special-structure rows were preserved without corporate verification.
- Real additive migration applied to the separate local preview database; the 311-row issuer file
  imported successfully with snapshot hash and no fabricated records.
- Banco de Bogotá resolved through the real RUES API at NIT **860002964**, DV **4**. Its RNVE key
  **001:001** matched by exact eligible NIT. The full capital-markets endpoint returned
  `registered_active`, `match_status=verified`, BVC listing `unknown`, and `equity_listed=null`.
- Its public SFC report returned **15 instruments**, ingested through the actual CLI. The securities
  endpoint paginated them as ten then five, with the correct lookahead flags.
- Bancolombia's distinct **001:007** public report parsed **18 rows** during discovery; its code was
  never used globally for other issuers.
- The documented optional smoke command passed against the official issuer workbook and Banco de
  Bogotá report, without a database or raw-record output.
- Isolated Chrome displayed the real company's Capital Markets tab and 15 instruments. Selecting
  corporate bonds returned seven rows through the running API. Desktop/mobile screenshots were
  inspected, with no horizontal page overflow at 390px (instrument tables scroll internally).
- BVC landing/local issuer pages returned HTTP 403. No private endpoint or access bypass was used.

Not verified live: cancelled/historical directory export formats, filtered-export coverage, combined
issuer/securities Excel/PDF formats, BVC current listings/tickers/ISINs, or ownership. These remain
explicit limitations. No government dependency was added to standard tests. Docker is unavailable
locally; Compose execution and GitHub CI for these changes are not claimed. Existing CI includes
the new tests and pinned parser dependencies; Docker configuration includes private report storage.

See [source discovery](capital-markets-sources.md) and [run/import/smoke commands](capital-markets.md).

Security-rename regression also passed: stable ANN/issuance/venue/date identifiers preserve the
instrument UUID while original names remain in source-record history. The real 15-instrument
report was refreshed after the identity refinement without duplicating instruments.

## Documentation, USD presentation and exports — 2026-11-24

Reviewed the repository against README, roadmap, References and feature documentation. Current
scope is in [the capability matrix](capabilities.md); earlier dated validation sections remain
historical evidence, not claims about current upstream availability.

Executed locally for this change:

- Backend Ruff lint/format and strict mypy; full pytest suite: 249 passed, 66 skipped. Skips include
  PostgreSQL-dependent tests (no disposable test database configured) and optional browser tests.
  Added a PostgreSQL export regression for actual filtering, precision, privacy and stale cap fallback;
  it is included in CI's database suite but was not executed locally.
- Frontend ESLint, TypeScript, Prettier, Vitest (133 passed) and production build; backend wheel
  packaging also passed. Build retains the existing
  large-bundle advisory; no new dependency was added.
- Exact division/half-even boundaries, invalid/expired/missing provider data, cache/cooldown,
  published validity intervals spanning days, failure behavior, explicit manual mode, CSV injection,
  quoting/newlines/Unicode, large decimals, export limits, snapshot/filter forwarding and safe projections.
- [Synthetic browser inspection](design/assets/currency-exports/README.md), EN/ES at
  320/390/768/1440px, manual USD and provider unavailable states, long company names, local scrolling,
  focus outline and References capability matrix. This is not a formal assistive-technology audit.
- A single bounded live call through the implemented TRM adapter returned `3505.92` COP per USD,
  effective 2026-11-24, with no stale/failure flag. No live company/source records were changed.

Source financial records, identity matching, existing migrations and original filter semantics were
not changed. Exported USD is optional presentation at the selected rate, never historical FX.

### Simplified Currency card — 2026-11-24

Replaced the disclosure with an always-visible top-right header card and COP/USD choices. USD
uses the editable effective TRM by default; edits are explicitly manual and an accessible refresh
arrow restores the reference. Removed the manual date field, moved calculation/provenance copy
into existing information tooltips, and replaced displayed COP amounts with ≈ USD in their original
elements/typography. Summary/chart/table currency labels now follow the displayed unit. Original
records, filters and export fields are unchanged.

Frontend lint, TypeScript, Prettier, production build and all 137 tests pass. Integration tests cover
summaries, charts, table, contract detail, quotes and authorized amounts, manual overrides/refresh,
failure/stale fallback, tooltips, mixed currencies and original filter/amount preservation. The
updated browser harness passed EN/ES at 320/390/768/1440px, checking no page overflow, USD replacement,
dynamic labels, visible focus and tooltip bounds/Escape dismissal. Screenshots are in the existing
[visual evidence directory](design/assets/currency-exports/README.md).

### Single export bar — 2026-11-24

Moved both research and filtered-contract exports into one pale-green bar above the company title.
The bar remains one line, with a scope selector and one Export button opening CSV/JSON choices;
limits and scope warnings remain in an information tooltip. Contract exports register the current
snapshot and filters with the header and remain disabled while table results update.

All 139 frontend tests, ESLint, TypeScript, Prettier and production build passed. Added coverage for
scope switching, current filtered requests, CSV/JSON choices, outside dismissal and Escape/focus
return. The EN/ES browser harness passed at 320/390/768/1440px, including bar placement, a single
control row, popup choices, tooltip bounds and no page-level overflow. Updated desktop/mobile
[visual references](design/assets/currency-exports/README.md) include the open export dropdown.

### Consistent custom dropdowns — 2026-11-24

Replaced every native select with the shared `Dropdown` combobox: currency, export scope,
Government Contracts filters/sort, Capital Markets filters and advanced-search modes. Replaced the
buyer's native datalist with the editable variant, preserving arbitrary input and exact original
suggestion values. Existing checkbox multi-selects now use matching popover styling and chevrons.
No backend/API, source identifiers, filter payloads or financial calculations changed.

All 144 frontend tests, ESLint, TypeScript, Prettier and the production build passed. New tests
cover keyboard navigation/commit/cancel, accented type-ahead, disabled options, focus, outside/Tab
dismissal, Unicode/raw values, editable suggestions and rendering outside clipping parents.
Existing filter, localization and currency regressions use real custom-dropdown interactions.
EN/ES browser checks passed at 320/390/768/1440px for currency, scope, contracts, Capital Markets and
advanced search, including no native selects/datalists, bounded popups and no page overflow.
Updated [visual references](design/assets/currency-exports/README.md) show expanded custom choices.

## RUES shared 60-second deadline — 2026-11-24

Raised the default and example/local settings to 60 seconds (the existing maximum). Company
search now enforces one deadline for RUES metadata, query, retries and backoff, rather than allowing
multiple full timeout windows. Cache persistence/recovery and optional BVC discovery remain outside
that upstream budget. External cancellation propagates. Timeout versus other transport failures
have distinct safe codes; retry logs include exception classes without query text or payloads.

Cached failures preserve the existing filters, evidence and stale flag with an explicit RUES
(Confecámaras / datos.gov.co) warning about outdated/incomplete records. No matching cache remains
503. EN/ES search errors name RUES; other modules keep source-specific error behavior. Legacy cached
warning strings are also rendered with the corrected copy.

Validation: backend Ruff/format, strict mypy, 262 passing tests (66 PostgreSQL/optional tests skipped
without a disposable test database/browser opt-in), frontend ESLint/TypeScript/Prettier, all 149
frontend tests, production frontend build and backend wheel build passed. New tests cover expiry
during metadata, query and real retry backoff, available/absent cache, external cancellation,
transport classification, default/limit validation, and rendered EN/ES fallback/error states.
The [synthetic browser review](design/assets/rues-timeout/README.md) passed all 16 combinations of
language, 320/390/768/1440px width and cached/no-cache outcome.

Restarted the local API with `SOCRATA_TIMEOUT=60`. A live request through the app proxy for the
reported “Thomas greg” query, without filters, returned HTTP 200, 9 records, `stale=false` and
`warning=null` in 20.96 seconds. This confirms the exercised request can complete beyond the old
20-second threshold; it does not guarantee future upstream response times.

## Rainbird Rae foundation — 2026-11-26

- Backend: 311 passed, 66 skipped (database/optional prerequisites not configured).
- Frontend: 154 passed across 11 files; ESLint, strict TypeScript, Prettier and production build pass.
- Ruff lint/format and strict mypy pass; Alembic has one head, migration applied to local DB,
  `alembic check` reports no new upgrade operations. Database readiness responds 200.
- EN/ES at 390, 768 and 1440px: no overflow or browser errors; dialog Escape returns focus.
  [Actual synthetic screenshots and inspection report](design/assets/rainbird/README.md).
- Explicit live smoke without credentials returns safe `not_configured`; no inference attempted.
  Native model deployment, Rae/reference decision agreement and live latency remain unverified.
- Vite warns about a bundle above 500 kB; build succeeds.
- Backend wheel built successfully. Read-only localhost company API smoke passed: disabled mode,
  no fabricated decisions, invalid screening-run ID returns 404; no external inference call.

## Frontend bundle splitting — 2026-11-26

Resolved Vite's 500 kB chunk warning with lazy secondary routes (company, parameters, references,
Rae methodology) and a cacheable React/router vendor chunk. Search remains eagerly available;
route-loading feedback uses centralized EN/ES text. No dependencies or warning-limit changes.
Before: one 599.10 kB JavaScript bundle (186.83 kB gzip). After: 255.71 kB app + 261.35 kB shared
runtime (167.38 kB gzip combined), with secondary page chunks loaded on demand. Build passes without
size warnings. All 154 frontend tests passed; ESLint, TypeScript and Prettier passed. Production
Chromium smoke confirmed secondary chunks are absent on the search page, standalone methodology
loads its chunk and renders successfully, and no browser exceptions occurred. No Core Web Vitals
or real-user speed improvement is inferred from these artifact-size measurements.

## Published Rae RBX adapter — 2026-11-26

Implemented the user-supplied published-build contract: Enterprise/RBX header, native JSON booleans,
optional field-specific conflict facts/end date, common and per-dimension diagnostics, build-ID pinning
without invented version metadata, optional-but-validated response session IDs, and bounded evidence
traversal fallback. Terminal outcome/sufficiency injection is rejected. The isolated synthetic CLI
has an explicit --live switch and checks outcomes, sufficiency and evidence completeness.

319 backend tests pass / 66 skip; strict mypy and Ruff lint/format pass. The private ignored
backend/.env was prepared with owner-only permissions and a blank key. Running --live without the
key returned not_configured without an inference call. Mocked RBX tests are contract validation,
not observed live Rae agreement. See [connection instructions](rainbird/RBX-connection.md).
