# Colombia Company Intelligence

An open-source platform for researching Colombian companies through their legal identity, registered
securities and government contracts. Search by name or NIT, uncover contracting patterns and counterparties,
and trace findings to official sources—turning fragmented public records into useful context for
business research.

![Colombia Company Intelligence — búsqueda, registro, valores inscritos y contratos del Gobierno](media/exports/colombia-company-intelligence-demo.gif?v=2)

Core company research demo. See the [current Government Involvement screenshots](docs/design/assets/rainbird/README.md)
for the latest reasoning interface.

## Implemented phases

**Phase 1 — Company identity:** search official RUES/Confecámaras records by NIT or legal name,
compare registration candidates, and inspect company identities, CIIU codes and registration dates.
Conservative identity matching, PostgreSQL caching and versioned source evidence preserve the
connection between each profile and its original record. See [company sources and schema](docs/sources.md).

**Phase 2 — Capital Markets:** connect verified company identities to SFC/RNVE issuer records,
registered securities, issuer details and source snapshots. Quote retrieval supports BVC,
La República and official SFC daily-price reports, with provider-specific identity checks,
source dates and fallback handling. See [Capital Markets operations](docs/capital-markets.md)
and [quote sources and verification](docs/quote-source-access.md).

**Phase 3 — Government Contracts:** query SECOP II electronic contracts by the company's verified
supplier NIT. The company profile includes contract totals and reported values in COP, contracting
entities, annual activity, all reported statuses, filters, sorting, five-contract pagination and
individual evidence with official source links. Successful results are cached for 24 hours;
explicit refreshes retain previous evidence when a source fails. Queries above the default
5,000-row cap show an alert without publishing partial totals. See [SECOP methodology, APIs and
source mapping](docs/secop-screening.md).

## Government Involvement · Rainbird AI's RAE

Government Contracts includes a bilingual Government Involvement card alongside the three activity
visualizations in a responsive 2×2 grid (stacked on mobile). It presents independent direct,
historical, recent and reported-execution conclusions, with evidence sufficiency for each.

- The lookback slider and typed input start at **24 calendar months**, with a range of **1–120 months**
  (10 years). Editing blanks the conclusions with skeletons; **Apply** evaluates the selected period.
  Editing alone never submits an evaluation or refreshes SECOP. Cache keys and standalone links retain
  the applied period.
- Conclusion information icons explain the methodology. Select a conclusion or **Learn more** to open
  **Government Involvement**, with matching outcome pills, a separate sufficiency glossary and compact
  evidence grouped by identity, dates, execution and coverage. Repeated facts are deduplicated;
  conflicting values and original source text remain visible. Original reasoning and supporting
  source observations start collapsed. Sources link to pinned contract details and official records.
- The popup header has **Open in new tab** and **Close** icons with localized tooltips and accessible
  labels. Escape or a backdrop click closes it and returns focus. The linked attribution is
  **Powered by Rainbird AI's RAE.** See the [popup action standard](docs/design/BRAND_AND_UI_GUIDELINES.md#popup-header-actions)
  and [responsive visual checks](docs/design/assets/rainbird/README.md).

Authorized company reasoning uses a successful verified SECOP II snapshot and a pinned published
Rainbird model. The backend transmits minimized structured facts and resolves witness references to
local evidence; company names, NITs, descriptions, amounts, official contract IDs and URLs are not sent.
Opening Government Contracts evaluates the snapshot or reuses cached decisions. **Refresh reasoning**
explicitly reevaluates it; **Refresh query** retrieves SECOP data. Prior findings remain available on
an evaluation failure, with stale/error notices. Disabled mode makes no company inference calls.

### Connect RAE and add the API key

For local backend commands, put `RAE_API_KEY` in the Git-ignored **`backend/.env`**. Development Compose
reads the repository-root **`.env`** instead; production reads the private external env file configured
by `CCI_ENV_FILE` (see the [deployment guide](docs/oracle-deployment.md)). Never add keys to frontend
variables, `.env.example` or source control.

Start from the settings in `.env.example`, then configure the API host and published build ID from
your model's connection guide. Company reasoning requires:

```dotenv
RAE_ENABLED=true
RAE_EXECUTION_MODE=live
RAE_COMPANY_PROCESSING_AUTHORIZED=true
RAE_API_BASE_URL=https://enterprise-api.rainbird.ai
RAE_ENGINE=rbx
RAE_MODEL_REFERENCE_MODE=published_build
RAE_MODEL_ID=your_published_build_id
RAE_API_KEY=your_platform_api_key
```

Leave `RAE_MODEL_VERSION` unset for published builds; update the build ID when republishing. Set
`RAE_EVIDENCE_KEY` only if your model requires it. Restart the backend after environment changes.
Repository examples keep company reasoning disabled. The [RAE manual](docs/RaeManual.md) and
[RBX connection guide](docs/rainbird/RBX-connection.md) cover policy, credentials, licensing, evidence
and activation checks. Synthetic and authorized company calls have been verified locally; this is
not a guarantee of model availability or production readiness for another deployment.

### Methodology and synthetic checks

Run `cd frontend && npm run dev -- --port 5174 --strictPort`, with the API on 8000 as below.
`/methodology/rae` explains the methodology without company processing;
[the separate synthetic example](http://localhost:5174/methodology/rae?demo=true) uses authored,
clearly labeled fixtures, not live RAE results. Its API endpoint needs no database.

To explicitly test the published model with fixed synthetic facts and private backend credentials:

```sh
cd backend
.venv/bin/python ../scripts/rae_smoke.py --live
```

`--live` enables `live_experimental` mode only for that CLI process; it does not enable company
transmission. Add `--persist` to save/reuse synthetic evaluations in PostgreSQL, or `--persist --refresh`
to bypass that cache. A declarative model specification and test-only Python reference are included;
company conclusions come from the published Rainbird model.

## Architecture

```mermaid
flowchart LR
    Browser[React + TypeScript · EN / ES] --> API[FastAPI v1]
    API --> Identity[Company identity and registration]
    API --> Markets[Capital Markets]
    API --> Contracts[Government Contracts · SECOP II]
    API --> References[References · local data readiness]
    Identity --> RUESAdapter[RUES adapter]
    Contracts --> SECOPAdapter[SECOP adapter · supplier NIT matching]
    RUESAdapter --> Client[Server-side HTTPX / Socrata]
    SECOPAdapter --> Client
    Client --> RUES[datos.gov.co · c82u-588k]
    Client --> SECOP[datos.gov.co · jbjy-vk9h]
    Markets --> MarketSources[SFC / RNVE · BVC · La República]
    Identity --> DB[(PostgreSQL)]
    Markets --> DB
    Contracts --> DB
    Contracts --> Involvement[Government Involvement · authorized backend service]
    Involvement --> DB
    Involvement --> Rae[Rainbird RAE · pinned REST model]
    Synthetic[Explicit synthetic-only CLI] --> Rae
    Rae --> Native[Native decisions and evidence]
    Native --> Involvement
    References --> DB
```

Backend: Python 3.12+, FastAPI/Pydantic v2, SQLAlchemy 2 async sessions, asyncpg, Alembic, HTTPX,
pytest/pytest-asyncio, Ruff, strict mypy. Frontend: React/strict TypeScript, Vite, Tailwind CSS,
TanStack Query, React Router, react-i18next, Vitest/Testing Library. Infrastructure: PostgreSQL 16, Docker Compose,
Make, and GitHub Actions. Rainbird RAE is an optional external service with separate credentials
and licensing. No Redis or Celery is required.

The canonical company UUID is **registration-scoped** in Phase 1. NIT is indexed but never a primary
key or unique key. Different registration rows sharing a NIT remain separate candidates. The
source system row ID identifies cached registrations; changed payloads retain auditable versions.
See [architecture](docs/architecture.md) and [verified source schema](docs/sources.md).

## Start with Docker

For public Oracle VM hosting, use the separate [production deployment guide](docs/oracle-deployment.md)
and `compose.production.yml`. It includes HTTPS/static hosting, private Postgres/API networking,
request limits, deployment scripts and verified backups. The Compose setup below is for development.

Prerequisite: Docker Engine/Desktop with Compose v2, plus Git. From the repository root:

```sh
cp .env.example .env
docker compose up --build --wait --wait-timeout 120
# Or: make up
docker compose logs -f backend
```

Open [the application](http://127.0.0.1:5173), [OpenAPI docs](http://127.0.0.1:8000/docs), or
[readiness](http://127.0.0.1:8000/ready). Compose waits for PostgreSQL, runs `alembic upgrade head`
in a one-shot service, then waits for the API and frontend HTTP health checks to pass.
First builds require package-network access;
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
# Backend commands run inside backend/ and read backend/.env, not the root file:
cp -n .env backend/.env  # Preserve any existing private backend settings.
# Exported variables override that file if needed:
export DATABASE_URL=postgresql+asyncpg://cci:cci@localhost:5432/cci
make migrate
make backend
# In a second terminal at repository root:
make frontend
```

Both `.env` files are ignored by Git; copy the example only for initial setup and preserve existing
private settings on updates. Pydantic reads `.env` relative to the working directory, and exported
environment variables take precedence. `make frontend` uses Vite's default port 5173; for port 5174,
use the explicit command above. Both loopback origins are allowed by the development defaults.
`make install` installs pinned Python dependencies, Chromium for RNVE summary rendering, and frontend
packages with `npm ci`. On Linux, first install browser system libraries using
`backend/.venv/bin/python -m playwright install --with-deps --no-shell chromium`. The frontend lockfile is
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
| `SOCRATA_TIMEOUT` | Default/max 60 seconds. Shared RUES lookup deadline covers metadata, network requests and retry waits; also bounds individual Socrata transport I/O phases. |
| `SOCRATA_RETRIES` | 2 retries, maximum 4; transient/network failures only |
| `UPSTREAM_CONCURRENCY` | 4 active upstream operations per API process |
| `CORS_ORIGINS` | JSON list; allows `localhost` and `127.0.0.1` on ports `5173` and `5174` by default |
| `API_PROXY_TARGET` | Frontend dev proxy target, normally `http://127.0.0.1:8000` |
| `CAPITAL_MARKETS_STORAGE_DIR` | Private regulatory report storage; defaults to `var/capital-markets` |
| `CAPITAL_MARKETS_MAX_AGE_HOURS` | Snapshot freshness threshold, default 24 hours; not a publishing-frequency guarantee |
| `CAPITAL_MARKETS_TIMEOUT`, `CAPITAL_MARKETS_RETRIES` | 30-second report/summary deadline; 2 HTTP report retries. Both sources use a 15-minute failure cooldown. |
| `SECOP_CACHE_HOURS` | Successful Government Contracts cache TTL, default 24 hours |
| `SECOP_MAX_ROWS` | Supplier-query row cap, default 5,000; larger portfolios show an alert without partial totals |
| `SECOP_RUN_TIMEOUT` | SECOP retrieval and persistence deadline, default 90 seconds |
| `BVC_CACHE_MINUTES`, `BVC_PAGE_URLS` | Quote cache TTL (15 minutes); optional verified ANN-code → BVC page URL mapping |
| `ADMIN_IMPORT_TOKEN` | Optional server-only token for administrator RNVE imports from non-loopback clients; minimum 32 characters |
| `RAE_ENABLED`, `RAE_EXECUTION_MODE` | `false` / `disabled`; authorized company evaluation uses `true` / `live`, synthetic CLI uses `live_experimental` |
| `RAE_COMPANY_PROCESSING_AUTHORIZED` | `false`; explicit authorization gate for minimized company fact transmission |
| `RAE_API_BASE_URL` | Set from the connection guide; repository env examples use Enterprise, while the code fallback is Community |
| `RAE_API_KEY`, `RAE_EVIDENCE_KEY` | Private backend Platform key and optional additional evidence key |
| `RAE_ENGINE`, `RAE_MODEL_REFERENCE_MODE`, `RAE_MODEL_ID` | `rbx`, `published_build`, and the model's published build ID |
| `RAE_MODEL_VERSION` | Unset for published builds; positive integer only for legacy `version` mode |
| `RAE_REQUEST_TIMEOUT_SECONDS`, `RAE_CACHE_HOURS` | 30-second inference deadline and 24-hour successful-evaluation cache by default |
| `GOVERNMENT_INVOLVEMENT_LOOKBACK_MONTHS` | API default 24, bounded 1–120; per-request `lookback_months` overrides it; card starts at 24 |
| `REFRESH_MIN_INTERVAL_SECONDS` | Explicit refresh cooldown, default 60 seconds; rejected retries report `Retry-After` |
| `RATE_LIMITS_ENABLED`, `SEARCH_REQUESTS_PER_MINUTE`, `REFRESH_REQUESTS_PER_MINUTE` | Request limits: disabled in local defaults, mandatory in production; budgets default to 30 searches and 6 refreshes per minute |
| `TEST_DATABASE_URL` | Separate disposable database used only by PostgreSQL tests |

Never commit `.env`, tokens, database files, or unreviewed raw source-record fixtures. Do not prefix source
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
keys, version uniqueness constraints, NIT/name indexes, and prefix search indexes. Phase 3 adds
screening runs, normalized SECOP contract evidence and run-to-contract snapshot membership.
Rainbird migrations add append-only evaluation history and the company/run/time lookup index.
API startup does not silently create schema. The source is registered lazily on its first search or `/sources` call.

## API

| Endpoint | Behavior |
|---|---|
| `GET /api/v1/companies?q=...&page=1&page_size=20` | NIT/name candidates, match evidence, pagination, source and stale warnings |
| `GET /api/v1/companies/{UUID}` | Identity, available registration/CIIU data, field states, source and freshness |
| `GET /api/v1/companies/{UUID}/sources` | Allowlisted source versions, source row ID, hashes, timestamps, mappings |
| `GET /api/v1/companies/{UUID}/capital-markets` | Local RNVE findings, independent BVC/ownership states, summary and provenance |
| `GET /api/v1/companies/{UUID}/securities` | Paginated registered instruments with category/venue/listing-status filters |
| `GET /api/v1/companies/{UUID}/screening/secop` | Cached Government Contracts outcome, verified summary, source metadata and freshness |
| `POST /api/v1/companies/{UUID}/screening/secop/refresh` | Explicit SECOP refresh with concurrency protection and rate controls |
| `GET /api/v1/companies/{UUID}/screening/secop/contracts` | Verified contracts with bounded pagination, search, status/entity/year/modality filters and date/value sorting |
| `GET /api/v1/companies/{UUID}/screening/secop/contracts/{contract_id}` | Company-scoped contract evidence and its official source link |
| `GET /api/v1/companies/{UUID}/screening/secop/involvement` | Cached or newly evaluated company reasoning; optional `run_id` and integer `lookback_months=1..120` |
| `POST /api/v1/companies/{UUID}/screening/secop/involvement/refresh` | Explicit same-origin reevaluation with the same scope parameters, cooldown and prior-result retention |
| `GET /api/v1/government-involvement/demo` | Authored synthetic conclusions/evidence; no database or external inference |
| `GET /api/v1/presentation/usd-rate` | Published effective SFC TRM for optional USD presentation |
| `GET /api/v1/companies/{UUID}/exports/research` | Company research CSV/JSON with provenance; `format=csv\|json` |
| `GET /api/v1/companies/{UUID}/exports/contracts` | All filtered contracts in a pinned snapshot, within export limits; `format=csv\|json` |
| `POST /api/v1/admin/imports/rnve` | Guarded official issuer-directory import, with XLSX upload fallback; see the Capital Markets guide |
| `GET /api/v1/platform` | Local data readiness and recorded source activity for the References page |
| `GET /api/v1/capital-markets/issuers` | Local issuer directory search by NIT/name |
| `GET /api/v1/capital-markets/sources` | Ingestion availability, attempts/successes, snapshots and freshness |
| `GET /api/v1/parameters` | Verified fixed-filter codes, descriptions, and catalog provenance |
| `GET /api/v1/sources` | Registered source metadata, availability and check/update timestamps |
| `GET /health` | Process liveness |
| `GET /ready` | Database connectivity; returns 503 on failure |

```sh
curl --get http://127.0.0.1:8000/api/v1/companies --data-urlencode 'q=890001255'
curl --get http://127.0.0.1:8000/api/v1/companies --data-urlencode 'q=URBANIZADORA LA SUIZA' --data 'page_size=10'
# Use the UUID returned by search, not a NIT:
curl http://127.0.0.1:8000/api/v1/companies/REPLACE_WITH_RETURNED_UUID
```

For company search, query length is 2–160 characters, page size is 1–50 and page is 1–100.
Source requests use stable row ordering
and a one-row lookahead, not a costly total count. Live results are ranked by RUES across all
matching source records before LIMIT/OFFSET pagination; the API preserves that order. Name ordering
prioritizes exact full names, equivalent normalized full names, whole-word phrases at the beginning,
whole-word phrases elsewhere, word prefixes, and remaining substrings. Ties use normalized name,
uppercase legal name, and source row ID. A supplied NIT verification digit is prioritized globally.
Cached fallback retains page-local matching order and explicitly reports `ranking_scope` as
`current cached page`; live responses report `all matching source records`. Match types are `exact_nit`, `exact_legal_name`, `normalized_name`, `partial_name`, and
`unresolved`; there are no invented confidence percentages. An explicit conflicting/missing DV
returns an unresolved candidate. Invalid identifier syntax returns 422; a valid no-match returns an
empty 200 collection. Errors follow `{"error":{"code":"...","message":"..."}}`.

RUES company search has a single configurable network-phase deadline (`SOCRATA_TIMEOUT`, default/max
60 seconds), shared across metadata, the source query and retry waits. It does not grant every retry
a fresh 60-second window. Database work and optional BVC issuer discovery are separate operations.
Changing this environment setting requires restarting the API.
Transient failures get bounded exponential retries with jitter. `Retry-After` is honored; requests
that ask for a delay over 15 seconds return an explicit source error rather than retrying early.
Failures without usable cache return 503. Cached fallback is always marked stale, with a warning
identifying RUES (Confecámaras / datos.gov.co) and explaining that previous results can be outdated
or incomplete. Actual transport timeouts use `source_timeout`; connection/protocol failures use
`source_unavailable`. Neither failure means zero matching companies.
Profiles are cached evidence: they do not silently refresh against RUES when opened.

## Frontend

The home page provides keyboard-accessible NIT/name search, advanced filters, loading/error/empty
states, a responsive results table and pagination. Registration and renewal dates appear in results;
missing values retain their explicit presentation. Selecting a company opens its **Overview**,
**Capital Markets** and **Government Contracts** tabs. Navigation preserves the originating query and
page; the back link restores cached results. Search pages remain cached in memory for 30 minutes,
and submitting Search explicitly requests fresh results.

Overview presents legal identity, CIIU code, registration dates, a copy-NIT action and source evidence.
Capital Markets presents issuer registration, securities and available quotes with source-specific
refresh controls. Government Contracts presents SECOP summary cards, activity charts, a searchable
contract table, contract details and the Government Involvement card described above. Source-information
cards, supporting observations and methodology details start collapsed. Financial Information and Corporate Events remain marked as coming later.

### English and Spanish

The EN/ES control in the main navigation switches application text and date, number and currency
presentation. The selection persists across visits; browser preference is used initially, with
Spanish as fallback. Original third-party names, descriptions and source values are preserved.
See [localization conventions and testing](docs/localization.md).

### Platform References

The **Platform References** page at `/references` explains architecture, data readiness and technical
workflows for RUES, Capital Markets and SECOP II. It includes responsive diagrams, metric definitions
and collapsed workflow details. See [References and the technical glossary](docs/platform-references.md).

### Design system and visual review

Frontend development follows the [brand and UI guidelines](docs/design/BRAND_AND_UI_GUIDELINES.md)
and shared [design tokens](frontend/src/design-tokens.css). See the [prioritized UI/UX audit](docs/design/ui-ux-audit.md)
and [actual before/after screenshots and reproduction steps](docs/design/assets/README.md).

## Search and Capital Markets operations

### Advanced search

Advanced search supports multi-select registration statuses, chambers, legal organizations,
and registration categories, plus exact/prefix CIIU, registration/renewal date ranges, and exact/minimum
last renewed year. Expand **Advanced filters** and submit Search to apply. **Parameters** in the
header documents observed fixed codes and source meanings. All filters apply before source
pagination and remain in URLs/cache keys. See [advanced filter API, semantics, and catalog refresh](docs/advanced-filters.md).

### Issuer imports and refresh

For capital-markets ingestion, apply `make migrate`, download the official SFC **DESCARGAR EMISORES →
REPORTE EXCEL**, then run from `backend/`:

```sh
.venv/bin/python -m app.jobs.refresh_capital_markets --issuer-report /absolute/path/Emisores.xlsx --nit-format concatenated-dv
.venv/bin/python -m app.jobs.refresh_capital_markets --entity 001:001
```

The second command is a Banco de Bogotá example using that issuer's verified type/code; use the
selected issuer's own key for other entities. Imports default to incomplete coverage. Confirm an
unfiltered current report and its count before using `--complete-current --expected-count N`.
Report files are private, content-addressed, and excluded from Git. See the operating guide for
Docker imports, snapshot/identity semantics, source-access limitations and optional live checks.

RNVE contact/administration details and separate securities reports refresh automatically when opening **Capital Markets**
for a verified issuer. Local backend setup also requires
`backend/.venv/bin/python -m playwright install --no-shell chromium` (included in `make install`).
On Linux, add `--with-deps` to install browser system libraries. Docker installs these dependencies.
Successful summaries and securities reports are cached independently for 24 hours; failures are retained separately with a 15-minute retry
cooldown. Unknown and failed retrievals are not presented as fields absent from the source.
See [RNVE summary retrieval and source limitations](docs/capital-markets-sources.md#public-rnve-issuer-summary-details).

Source-information cards in Overview and Capital Markets start collapsed. Stale-data and
retrieval-failure alerts include **Refresh data** actions. Manual Capital Markets refresh uses
`GET /api/v1/companies/{id}/capital-markets?refresh=true` to bypass summary/report cache TTLs
and failure cooldowns while retaining concurrency limits and previous successful evidence.
The RNVE issuer directory still requires a new official export; a report refresh never relabels
that directory as current. Overview uses `GET /api/v1/companies/{id}?refresh=true` to retrieve
only the original RUES system row, preserving separate registrations even when NITs match.
Missing or mismatched rows and source failures preserve cached evidence and return an error.

Capital Markets refresh actions are source-specific: top alert buttons open and scroll to the
collapsed **Data Source Information** section; only the buttons inside each source perform a
refresh. They call `?refresh=true&refresh_source=sfc_rnve_issuer_details` or
`?refresh=true&refresh_source=sfc_rnve_securities`. A selected refresh never calls the other
connector. RNVE directory controls execute the guarded public-export import, with an official XLSX
upload fallback; see [import controls and References diagnostics](docs/capital-markets.md#migrate-and-import).
Alerts identify the affected source, last successful retrieval, source observation date, latest
attempt and recorded error. Summary/securities timestamps and errors are scoped to the current
issuer; the source-catalog endpoint continues to show global connector health.

### Quote providers and BVC discovery

BVC stock-summary support matches Código Superfinanciera exactly to registered common-equity ANN
codes and displays last reported price/ticker with provenance. Initial page-routing coverage is the
user-supplied Ecopetrol URL; `BVC_PAGE_URLS` adds other official page locators. `BVC_CACHE_MINUTES`
defaults to 15. The source guide records BVC HTTP 403 access assessments and the dated La República fallback;
synthetic contract tests cover extraction and matching without seeding example prices into the app.
See [BVC source and validation details](docs/capital-markets-sources.md#bvc-access-assessment).

La República now supplies dated public-browser stock quotes when primary BVC access fails. The
publisher, source quote time and exact NIT/ANN/legal-name evidence remain visible. Ecopetrol was
verified end to end. Stock URLs are discovered automatically from the publisher directory, cached
for 24 hours, and verified by exact identity; no per-company URL configuration is needed. Grupo Aval was reachable
but had an empty main quote table and no eligible row identity, so it is not activated as a fallback.
See [tested access paths and source feasibility](docs/quote-source-access.md).

The search **Registrado BVC** check and checkbox use verified issuer links plus RNVE
ordinary-share records with market BVC. Checked searches discover candidate issuers from the
imported RNVE directory, retrieve their securities evidence using the cache, then restrict live
RUES queries by eligible NIT **before pagination**. Newly searched companies need not have been
cached or opened in Capital Markets. A blank check cell is not a negative listing finding.
See [BVC search discovery and coverage](docs/capital-markets.md#bvc-registration-in-company-search).

Capital Markets quote retrieval falls back from BVC to La República and then to an official
SFC daily-price report, requiring exact identity evidence at every step. The card reports each
provider's outcome when unresolved. SFC values are explicitly labeled daily weighted averages,
with their source date; no last-trade price or ticker is invented. See [quote fallback verification](docs/quote-source-access.md#registered-ordinary-share-fallback-terpel-case).

## Tests and validation

```sh
make lint                  # Ruff lint/format, strict mypy, ESLint, strict TypeScript
make test                  # Unit/contracts/API tests + frontend; PG tests skip without a test URL
make test-db               # Disposable Compose PostgreSQL on 5433; real persistence/migration tests
make build                 # Production frontend assets + backend wheel
make smoke                 # Optional LIVE metadata + two filtered queries (one row each)
backend/.venv/bin/python scripts/live_smoke.py --ranking  # Also verify ranked page boundaries
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
backend packaging, a separate development Compose startup/readiness check, and production stack/backup
restoration smoke checks on x86-64 and ARM runners. Live government and Rainbird connectivity is
intentionally excluded from CI. See [validation notes](docs/validation.md) for executed local checks.

## Official data limitations and privacy

**RUES/Confecámaras:** source discovery verified 36 text columns. Available: legal name, nullable NIT/DV, chamber code/name,
matrícula, legal organization, status, primary/secondary/other CIIU codes, and registration/renewal/
cancellation/update dates. **Municipality and department do not exist in the verified schema.**
Chamber location is not used as a company address. This dataset has no verified CIIU descriptions,
capital-market fields or government-contract fields; SFC and SECOP provide the latter two through
independent connectors. Read the [RUES schema](docs/sources.md), [Capital Markets sources](docs/capital-markets-sources.md)
and [SECOP source mapping](docs/secop-screening.md).

Some rows are natural persons or cancelled registrations; NIT and dates can be missing, stale, or
malformed. Registration dates remain source strings in the API and audit records; the UI formats
valid dates and flags placeholders instead of interpreting them as actual events. Source timestamps
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
- **503 source failure:** the RUES lookup may have reached its 60-second deadline or encountered
  a connection/provider failure. Check official-host network access; add an optional app token if appropriate.
  Do not interpret an outage as zero companies. Retry later or use explicitly stale cache results.
- **No name candidates:** try a shorter distinctive source-spelled name; punctuation/accents can differ.
  A no-match is limited to this dataset and this bounded search.
- **Schema-changed error:** run `make smoke`, inspect current metadata, and update the adapter and tests
  after review. Do not map renamed fields speculatively.
- **Playwright image build fails with `libatomic.so.1`:** the bundled Node executable needs Debian's
  `libatomic1` before `playwright install --with-deps` can start. The backend Dockerfile installs
  this bootstrap dependency first; rebuild with `docker compose up --build --wait`.
- **Port occupied:** free 5432/8000/5173 (or 5174 when explicitly selected), or update Compose mappings
  and the dev proxy/CORS settings together.
- **New PostgreSQL credentials with old volume:** an existing volume retains its original credentials.
  Restore matching settings or intentionally recreate a disposable volume; do not delete valuable data.
- **Browser fetch error:** use the Vite proxy or configure an expected CORS origin. Tokens stay backend-only.
- **Refresh query/reasoning returns 403:** check the browser Origin against `CORS_ORIGINS`, including
  the exact scheme, hostname and port. Both `localhost` and `127.0.0.1` on 5173/5174 are development
  defaults; existing private env files may still contain older values. Restart after changing them.
  Production uses its same-origin HTTPS proxy and must not inherit development origins.
- **Refresh returns 429:** wait for `Retry-After`; the interface shows a retry countdown. Previous
  evidence stays available.
- **Reasoning unavailable/failed:** verify the private API key, published build ID, live mode and
  processing authorization, then ensure a successful current-policy SECOP snapshot exists. Review
  source/evaluation dates and the [RAE troubleshooting guide](docs/RaeManual.md#17-troubleshooting).
  Keys never belong in frontend variables.

## Current capabilities, presentation and exports

See the [capability matrix](docs/capabilities.md) for implemented, partial, experimental and planned
features, source coverage and limitations. Government Contracts is implemented SECOP II research;
it is not comprehensive screening. The default portfolio cap is 5,000 source rows, with no partial
new totals above the cap. SECOP currency is an explicit COP application convention.

Profiles offer [optional USD presentation](docs/currency-presentation.md) with a published effective
SFC TRM or an editable manual COP-per-USD rate in the top-right Currency card. USD replaces COP
on screen with `≈` estimates and matching currency labels; source amounts remain unchanged and are
retained in exports. USD estimates are not historical conversions. [CSV/JSON exports](docs/exports.md) include public
company research or all filtered contracts in a pinned snapshot, provenance, retrieval dates and
completeness warnings. Exports reject more than 1,000 rows or 5 MiB; stale evidence stays labeled. RAE conclusions and
native reasoning are available in the app and are not included in these exports.

The rate and export endpoints are listed in the API table above.

## Roadmap, license, and contributions

Company identity, Capital Markets and SECOP II Government Contracts are implemented. Next
engineering priorities include source contract monitoring, reviewed multi-registration reconciliation,
and deployment/privacy/browser-test hardening. Future work includes financial statements,
additional independently selectable screening sources and grounded briefings; see [the roadmap](docs/roadmap.md).

Code is [MIT licensed](LICENSE). Official data is separately attributed to Confecámaras under the
metadata's CC BY-SA 4.0 license; software permission does not relicense third-party data.
Contributions are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md).
