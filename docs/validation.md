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
- **66 backend tests passed**, including real PostgreSQL persistence, separate registration IDs,
  payload-version deduplication, foreign-key relationships, pagination, API profile/source routes,
  public-field filtering, cached normalized-name matching, source failure behavior, and migration
  upgrade → downgrade → re-upgrade → Alembic model-drift check.
- **6 frontend tests passed**: submit-only search, animated retrieval-dialog lifecycle, result/profile link rendering, source-error
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
  The GitHub Actions Compose job builds/starts the services and checks readiness; that workflow has
  been authored but **has not run on GitHub in this session**.
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
docker compose up --build -d
curl --fail http://127.0.0.1:8000/ready
curl --fail http://127.0.0.1:5173
```


Spacing-search regression validation adds compact/spaced query equivalence, escaped literals,
space-insensitive match classification, preservation of legal suffixes and separate identities,
pagination, cached matches during empty responses/outages, and previous-name alias recovery.
The full 66-test backend suite passed against PostgreSQL, including the additional expression-index
migration, downgrade/re-upgrade, and Alembic model-drift check.
