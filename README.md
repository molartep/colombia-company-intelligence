# Colombia Company Intelligence

An open-source, evidence-backed starting point for researching Colombian business identities.
Search by NIT or legal name, compare official registration candidates, and inspect a company profile
with source records, mappings, and separate retrieval/update timestamps.

**Phase 1 is implemented:** live server-side RUES/Confecámaras queries, conservative identity
resolution, PostgreSQL caching and raw audit records, a FastAPI API, and a responsive React UI.
There is no production demo data. Tests use clearly synthetic companies.

This phase does **not** determine ownership, securities listings, financial condition, acquisitions,
public procurement, regulatory findings, fiscal responsibility, or AI summaries. Those attributes
are marked not yet checked. A missing result is not evidence that an entity does not exist.

## Architecture

```mermaid
flowchart LR
    Browser[React + TypeScript\nTanStack Query / Router] --> API[FastAPI v1]
    API --> Service[Normalization + deterministic resolution]
    Service --> DB[(PostgreSQL 16\nCompanies / aliases / raw records)]
    Service --> Adapter[RUES adapter]
    Adapter --> Client[HTTPX SocrataClient]
    Client --> RUES[datos.gov.co\nc82u-588k / SODA 2.x]
```

Backend: Python 3.12+, FastAPI/Pydantic v2, SQLAlchemy 2 async sessions, asyncpg, Alembic, HTTPX,
pytest/pytest-asyncio, Ruff, strict mypy. Frontend: React/strict TypeScript, Vite, Tailwind CSS,
TanStack Query, React Router, Vitest/Testing Library. Infrastructure: PostgreSQL 16, Docker Compose,
Make, and GitHub Actions. No paid services, Redis, Celery, or distributed infrastructure.

The canonical company UUID is **registration-scoped** in Phase 1. NIT is indexed but never a primary
key or unique key. Different registration rows sharing a NIT remain separate candidates. The
source system row ID identifies cached registrations; changed payloads retain auditable versions.
See [architecture](docs/architecture.md) and [verified source schema](docs/sources.md).

## Start with Docker

Prerequisite: Docker Engine/Desktop with Compose v2, plus Git. From the repository root:

```sh
cp .env.example .env
docker compose up --build -d
# Or: make up
docker compose logs -f backend
```

Open [the application](http://127.0.0.1:5173), [OpenAPI docs](http://127.0.0.1:8000/docs), or
[readiness](http://127.0.0.1:8000/ready). Compose waits for PostgreSQL, runs `alembic upgrade head`
in a one-shot service, then starts the API and frontend. First builds require package-network access;
searches require access to `www.datos.gov.co`. An app token is optional.

```sh
docker compose down                # Stop; keep database volume
# Or: make down
docker compose run --rm migrate    # Apply pending migrations after an update
docker compose logs migrate db backend
```

`docker compose down -v` deletes local database data. Use it only when intentionally resetting a
disposable environment. The frontend container uses Vite for the local development workflow; it
is not a hardened public web server. All exposed ports bind to loopback.

## Run outside Docker

Use Python 3.12+ (3.12 recommended), Node 24, and PostgreSQL 16+ on Linux/macOS. On Windows,
use Docker/WSL. The commands below use a disposable local role/database with development credentials:

```sh
cp .env.example .env
# If PostgreSQL is installed locally, as a PostgreSQL administrator:
createuser --pwprompt cci
createdb --owner=cci cci
# Or start only the Compose database:
docker compose up db -d --wait

make install
# If your Python executable is named differently, substitute it in the Makefile's venv command.
# Export root .env values for processes started in backend/:
export DATABASE_URL=postgresql+asyncpg://cci:cci@localhost:5432/cci
make migrate
make backend
# In a second terminal at repository root:
make frontend
```

Alternatively copy `.env` to `backend/.env` for backend commands; it is ignored by Git. Pydantic
reads `.env` relative to the working directory, and exported environment variables take precedence.
`make install` uses pinned Python development dependencies and `npm ci`; the frontend lockfile is
committed. Runtime and dev lockfiles were resolved on Python 3.12 for Linux/macOS; re-resolve when
upgrading Python or dependencies. Production Docker installs the smaller runtime lockfile.

The Vite development proxy forwards `/api` to `http://127.0.0.1:8000`. In Compose it uses the internal
backend host. Production static hosting requires SPA routing fallback and a same-origin `/api` proxy.
The frontend never calls Socrata directly.

## Configuration

| Variable | Default / purpose |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://cci:cci@localhost:5432/cci`; Compose overrides the host internally |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Local Compose database credentials; change before deployment |
| `SOCRATA_APP_TOKEN` | Optional server-only token, sent via `X-App-Token` |
| `SOCRATA_TIMEOUT` | 20 seconds per upstream attempt; positive, maximum 60 |
| `SOCRATA_RETRIES` | 2 retries, maximum 4; transient/network failures only |
| `UPSTREAM_CONCURRENCY` | 4 active upstream operations per API process |
| `CORS_ORIGINS` | JSON list; allows `localhost:5173` and `127.0.0.1:5173` by default |
| `API_PROXY_TARGET` | Frontend dev proxy target, normally `http://127.0.0.1:8000` |
| `TEST_DATABASE_URL` | Separate disposable database used only by PostgreSQL tests |

Never commit `.env`, tokens, database files, or real source-record fixtures. Do not prefix source
tokens with `VITE_`. Short controlled queries, fixed upstream hosts, parameterized SQL, request limits,
sanitized errors, private raw records, and allowlisted public fields reduce accidental disclosure.
Launch the API with `--no-access-log` as in Make/Compose; reverse proxies must also avoid query logging.

## Database migrations

```sh
cd backend
.venv/bin/alembic upgrade head
.venv/bin/alembic current
.venv/bin/alembic check
# After an intentional model change:
.venv/bin/alembic revision --autogenerate -m "Describe schema change"
# Review generated code before use; downgrade deletes changed tables/data as specified:
.venv/bin/alembic downgrade -1
```

Migrations create companies, aliases, data sources, source records, UUID keys, JSONB storage, foreign
keys, version uniqueness constraints, NIT/name indexes, and prefix search indexes. API startup does
not silently create schema. The source is registered lazily on its first search or `/sources` call.

## API

| Endpoint | Behavior |
|---|---|
| `GET /api/v1/companies?q=...&page=1&page_size=20` | NIT/name candidates, match evidence, pagination, source and stale warnings |
| `GET /api/v1/companies/{UUID}` | Identity, available registration/CIIU data, field states, source and freshness |
| `GET /api/v1/companies/{UUID}/sources` | Allowlisted source versions, source row ID, hashes, timestamps, mappings |
| `GET /api/v1/sources` | Registered source metadata, availability and check/update timestamps |
| `GET /health` | Process liveness |
| `GET /ready` | Database connectivity; returns 503 on failure |

```sh
curl --get http://127.0.0.1:8000/api/v1/companies --data-urlencode 'q=890001255'
curl --get http://127.0.0.1:8000/api/v1/companies --data-urlencode 'q=URBANIZADORA LA SUIZA' --data 'page_size=10'
# Use the UUID returned by search, not a NIT:
curl http://127.0.0.1:8000/api/v1/companies/REPLACE_WITH_RETURNED_UUID
```

Query length is 2–160 characters; page size 1–50; page 1–100. Source requests use stable row ordering
and a one-row lookahead, not a costly total count. Results rank deterministically within the current
bounded page. Match types are `exact_nit`, `exact_legal_name`, `normalized_name`, `partial_name`, and
`unresolved`; there are no invented confidence percentages. An explicit conflicting/missing DV
returns an unresolved candidate. Invalid identifier syntax returns 422; a valid no-match returns an
empty 200 collection. Errors follow `{"error":{"code":"...","message":"..."}}`.

Transient failures get bounded exponential retries with jitter. `Retry-After` is honored; requests
that ask for a delay over 15 seconds return an explicit source error rather than retrying early.
Failures without usable cache return 503. Cached fallback is always marked stale, with a warning.
Profiles are cached evidence: they do not silently refresh against RUES when opened.

## Frontend

The home page provides a submit-only, keyboard-accessible NIT/name search, loading/error/empty states,
a responsive candidate table, and pagination. Selecting a UUID opens Overview and Sources sections.
Overview includes identity, CIIU code, registration strings, a copy-NIT button, freshness, and attribute
availability. Sources includes official links, safe public fields, source row IDs, mappings in the
API, and payload hashes. Future sections are marked coming later. No financial or screening results
are fabricated. The UI is in English; official company names and labels retain their source spelling.

## Tests and validation

```sh
make lint                  # Ruff lint/format, strict mypy, ESLint, strict TypeScript
make test                  # Unit/contracts/API tests + frontend; PG tests skip without a test URL
make test-db               # Disposable Compose PostgreSQL on 5433; real persistence/migration tests
make build                 # Production frontend assets + backend wheel
make smoke                 # Optional LIVE metadata + two filtered queries (one row each)
```

To run the entire backend suite with your own disposable database:

```sh
cd backend
TEST_DATABASE_URL=postgresql+asyncpg://cci:cci@localhost:5433/cci_test .venv/bin/pytest -q
```

**Database tests downgrade/re-upgrade and truncate their target tables. Never point them at a
production/development database you need to keep.** Standard tests use mocked HTTPX responses,
including missing/malformed fields, schema drift, 429, 5xx, timeouts, no matches, and controlled query
escaping. PostgreSQL tests verify actual migrations, uniqueness, row relationships, versions,
pagination, stale fallback, and the end-to-end API with synthetic data. Frontend tests cover form
submission and loading-dialog behavior, results, source failures, empty states, and profile rendering.

CI runs the full backend suite against PostgreSQL 16, lint/type checks, frontend tests/build,
backend packaging, and a separate Compose startup/readiness check. Live government connectivity is
intentionally excluded from CI. See [validation notes](docs/validation.md) for executed local checks.

## Official data limitations and privacy

Source discovery verified 36 text columns. Available: legal name, nullable NIT/DV, chamber code/name,
matrícula, legal organization, status, primary/secondary/other CIIU codes, and registration/renewal/
cancellation/update dates. **Municipality and department do not exist in the verified schema.**
Chamber location is not used as a company address. There are no verified CIIU descriptions or
capital-markets/financial/screening fields. Read the [full schema and limitations](docs/sources.md).

Some rows are natural persons or cancelled registrations; NIT and dates can be missing, stale, or
malformed. Registration dates remain source strings, including sentinel values. Source timestamps
lack timezone metadata; Colombia time is an explicitly documented interpretation. Names normalize
for comparison, without stripping legal suffixes. Name searches ignore word-spacing differences
(for example, `olartemoure` matches `OLARTE MOURE`); this is candidate matching, never entity merging.
Remote accent-insensitive matching is not claimed;
exact cached normalized aliases can recover previously consulted variants, with a cache warning.
Source IDs may change on publisher replacement, and offset pages may shift as the dataset changes.

Raw records are private audit data, not public API payloads. Public availability does not establish
unrestricted redistribution rights. Review lawful usage, database access, logs, backups, retention,
and deletion before public operation. The local foundation has no authentication or automatic data
retention policy and should not be deployed openly without those controls. Missing data is never a
verified negative finding. Nothing here substitutes for an authoritative registry extract.

## Troubleshooting

- **503 database unavailable:** verify PostgreSQL is running, URL/credentials are correct, and migrations
  ran. Inspect `docker compose logs db migrate backend`. Readiness checks connectivity, not RUES.
- **503 source failure:** check official-host network access; add an optional app token if appropriate.
  Do not interpret an outage as zero companies. Retry later or use explicitly stale cache results.
- **No name candidates:** try a shorter distinctive source-spelled name; punctuation/accents can differ.
  A no-match is limited to this dataset and this bounded search.
- **Schema-changed error:** run `make smoke`, inspect current metadata, and update the adapter and tests
  after review. Do not map renamed fields speculatively.
- **Port occupied:** free 5432/8000/5173 or update Compose mappings and the dev proxy/CORS settings together.
- **New PostgreSQL credentials with old volume:** an existing volume retains its original credentials.
  Restore matching settings or intentionally recreate a disposable volume; do not delete valuable data.
- **Browser fetch error:** use the Vite proxy or configure an expected CORS origin. Tokens stay backend-only.

## Roadmap, license, and contributions

See [the roadmap](docs/roadmap.md) for capital markets, financials, selectable screening, and grounded
briefings. Next priorities are source contract monitoring, reviewed multi-registration reconciliation,
and deployment/privacy/browser-test hardening. These future modules are not implemented now.

Code is [MIT licensed](LICENSE). Official data is separately attributed to Confecámaras under the
metadata's CC BY-SA 4.0 license; software permission does not relicense third-party data.
Contributions are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md).
