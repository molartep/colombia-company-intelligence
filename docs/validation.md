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
- **70 backend tests passed**, including real PostgreSQL persistence, separate registration IDs,
  payload-version deduplication, foreign-key relationships, pagination, API profile/source routes,
  public-field filtering, cached normalized-name matching, source failure behavior, and migration
  upgrade → downgrade → re-upgrade → Alembic model-drift check.
- **26 frontend tests passed**: submit-only search, animated retrieval-dialog lifecycle, result/profile link rendering, NIT column separation, registration-status colors, source-error
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

- Government requests intermittently timed out. The 20-second default can trigger stale fallback;
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
