# SECOP II supplier screening (Phase 3)

The company profile’s **Screening** tab queries public electronic contracts associated with the selected company’s source-confirmed NIT. It describes procurement participation, not sanctions, corruption, fraud, or a company risk score. SECOP I, consortium membership attribution and other future sources are outside this phase.

## Official source validation

Publisher: Agencia Nacional de Contratación Pública — Colombia Compra Eficiente.

- [Dataset](https://www.datos.gov.co/Gastos-Gubernamentales/SECOP-II-Contratos-Electr-nicos/jbjy-vk9h)
- [Metadata API](https://www.datos.gov.co/api/views/jbjy-vk9h.json)
- [Resource API](https://www.datos.gov.co/resource/jbjy-vk9h.json)
- Repository snapshot: `docs/discovery/secop-metadata.json` (metadata only; no personal records).

Validation on November 18, 2026 retrieved the metadata and five bounded general sample records, then ten bounded records filtered to supplier document type `NIT`. The initial sample included `Cédula de Ciudadanía`; NIT-filtered samples used `NIT`, nine bare digits without an explicit verification digit, and `es_grupo=No`. Values included zero and fractional decimals. These observations do not establish every identifier format in the entire dataset. An additional live adapter check for one explicitly selected NIT returned 12 rows and 12 unique verified contracts; the source timestamp reported during that check was `2026-11-18T23:36:18Z`.

### Verified field mapping

| Meaning | API field | Socrata type / definition |
|---|---|---|
| Supplier document | `documento_proveedor` | text; document number of awarded supplier |
| Supplier document type | `tipodocproveedor` | text; awarded supplier document type |
| Group supplier | `es_grupo` | text; whether supplier is a group of entities |
| Contract ID | `id_contrato` | text; platform-generated signed contract identifier |
| Process ID | `proceso_de_compra` | text; published procurement process identifier |
| Buyer’s reference | `referencia_del_contrato` | text; entity-generated contract identifier |
| Buyer | `nombre_entidad` | text; state entity publishing the contract |
| **Buyer NIT, never supplier matching** | `nit_entidad` | number; NIT of state entity publishing the contract |
| Contract value | `valor_del_contrato` | number; “Valor total del contrato” |
| Raw status | `estado_contrato` | text; execution/signature/liquidation state |
| Signature | `fecha_de_firma` | calendar_date; electronic contract signature |
| Start / end | `fecha_de_inicio_del_contrato`, `fecha_de_fin_del_contrato` | calendar_date; contractual responsibilities |
| Contract type | `tipo_de_contrato` | text |
| Modality | `modalidad_de_contratacion` | text |
| Description | `objeto_del_contrato`, fallback `descripcion_del_proceso` | text; contract object / process description |
| Buyer geography | `departamento`, `ciudad` | text; location of the publishing state entity, **not necessarily place of performance** |
| Process link | `urlproceso` | url; link to procurement process, **not a verified contract permalink** |
| Contract update | `ultima_actualizacion` | calendar_date; electronic contract last update |
| Source row identity | `:id` aliased `source_row_id` | Socrata system row ID; live retrieval validated |
| Dataset update | metadata `rowsUpdatedAt` | Unix timestamp; checked before and after pagination |
| Currency | **absent** | Application convention: COP; not supplied by the source |

The complete metadata snapshot contains descriptions of all published fields. Runtime validates every field selected by the connector against this mapping. A schema change fails the screening instead of yielding a false clean finding. The connector deliberately omits names/IDs of representatives, bank accounts, addresses and other unnecessary personal data.

## Matching and scope

The company must have a confirmed nine-digit canonical base NIT and a stable Phase 1 source identity. The existing `normalize_nit` utility preserves leading zeroes and removes valid dot/space separators. SECOP then applies the explicit digit-count matching rule:

- **Nine supplier digits:** exact equality with the company's nine-digit base NIT (exclude the company's DV from this comparison).
- **Ten supplier digits:** exact equality with the company's nine-digit base NIT plus its confirmed DV, including bare concatenated identifiers. A missing or conflicting company DV prevents a ten-digit match.
- Other lengths or malformed identifiers are excluded. No checksum or DV is invented; no suffix of a different base NIT is discarded.

Supplier document type must be `NIT` and the supplier must explicitly be non-group (`es_grupo=No`). Supplier names and buyer NITs cannot produce matches. The upstream predicate uses escaped equality `IN` literals for the bare base, bare base+DV, conventional dotted/spaced groupings, and explicit hyphen+DV variants, never substring queries. This is a bounded set of formatting variants, not unrestricted punctuation removal upstream.

Matching policy `supplier_nit_9_base_10_with_dv_v1` is recorded with new runs. Earlier cached successes remain visible with a stale warning prompting refresh, because their queries did not include concatenated ten-digit identifiers. A refresh is required to discover newly eligible source records; existing cache timestamps are preserved.

Each normalized contract preserves source row ID, original and normalized supplier identifier, document type, exact matching method/status, observation timestamp, and evidence ID.

## Retrieval, deduplication and amounts

1. Validate metadata and source update timestamp.
2. Issue an official SoQL `count(*)` for the selective supplier predicate.
3. Refuse to retrieve more than `SECOP_MAX_ROWS` (default 5,000; maximum configurable 10,000). No partial totals are published.
4. Retrieve only selected audit fields in pages of 200, explicitly ordered by `:id ASC`.
5. Verify expected row count, distinct source row identities, and unchanged dataset update timestamp. These checks reduce pagination drift; Socrata does not provide a transaction snapshot, so undetected source changes remain possible.
6. Filter exact supplier identity locally; deduplicate on `id_contrato`. Prefer the observation with the latest explicit `ultima_actualizacion`. Identical duplicates count once. Conflicting tied versions, or conflicting version histories with missing ordering timestamps, are excluded with an exclusion warning.
7. Persist the complete bounded verified snapshot and compute deterministic aggregates from that snapshot.

The schema has no explicit amendment/version chain. “Latest observation” is an observation policy, not proof of which amendments supersede others. Source values cannot be identified reliably as original, modified, or cumulative amounts; the UI labels them as reported total contract values.

All values use Python `Decimal`, PostgreSQL `NUMERIC(31,6)`, and JSON decimal strings. Negative, non-finite, malformed, excessively large, or more-than-six-fractional-digit values are excluded from monetary aggregation but their verified contracts remain in counts. Zero is valid and explicitly counted. The application explicitly interprets SECOP amounts as **Colombian pesos (COP)** at the user's direction. This is an application convention, not a currency field verified in the source. Normalized evidence records `currency=COP` and `currency_basis=application_policy`, while raw source evidence remains unchanged. Totals and annual values use precise decimals; top buyers rank by COP contract value, with count/name tiebreakers. Different explicit currencies, if introduced later, remain separate with no conversion. The API reports how many records have missing/invalid values, unknown currency, zero values, or eligibility for monetary totals.

Counts, signature-date annual activity, all reported source statuses without an Other bucket, buyer count, modalities, buyer geography, and the five buyers by COP contract value are available. Missing signature dates have their own annual bucket and are never replaced with start or update dates. The status chart and its table filter use the exact reported `estado_contrato` text (outer whitespace trimmed). Every distinct status is shown, including single-contract statuses; there is no top-N or Other grouping. Only missing or blank statuses use `No informado`. Internal normalized categories remain available through the existing API `status` filter, and none implies payment. Cached summaries using older status categories are recomputed from their persisted contracts on read (`summary_policy=raw_status_groups_v1`) without contacting SECOP or changing freshness timestamps. Buyer counts prefer buyer NIT and fall back to normalized buyer name when missing.

Socrata aggregation is used for the bounded retrieval preflight. Summing upstream values would count duplicates and bypass identity exclusions. Therefore final summaries use the fully materialized, verified snapshot rather than an unsafe upstream sum. The cap remains at 5,000 source rows for now. Portfolios above it display a prominent alert near the top of Screening explaining that the query could not be completed and no partial totals are published. Any previous successful result remains visible with a stale-data notice. Supporting larger portfolios is deferred.

## Persistence and lifecycle

Migration `8b90ad124a01` adds:

- `screening_runs`: company, source, canonical NIT, running/completed/failed state, start/completion times, source timestamp, query/matching metadata, summary, warnings and safe error code. The schema also permits pending for future job integration.
- `secop_contracts`: normalized evidence projection with indexed contract ID, buyer, status, modality, signature date and precise value; unique evidence reference.
- `screening_contracts`: snapshot membership, indexed by run and contract primary key.

Existing `data_sources` and content-addressed `source_records` store attribution and minimized raw evidence. Repeated snapshots reuse unchanged evidence/projections. The currency policy is versioned in run metadata (`secop_cop_v1`). Cached results from the earlier currency-unavailable policy are recomputed from their existing local verified evidence on read, without a source request or changes to original evidence/freshness timestamps; details apply the same convention. Run membership owns company association; SECOP source records leave `company_id` empty to avoid contaminating Phase 1’s registry-only latest-record selection. Contract details verify run/company/source/NIT ownership; callers cannot retrieve another company’s contracts by guessing IDs. `run_id` optionally pins both table pages and details to a successful snapshot.

Refresh follows the existing synchronous request approach, with no additional queue. A PostgreSQL nonblocking transaction advisory lock per company/source prevents concurrent refreshes across processes. The running row and evidence are published atomically at commit. While another request holds the refresh lock, GET reports `running`; the frontend polls every two seconds. Before commit, a newly started run’s exact timestamp/ID is not visible to other requests. Requests have a configurable timeout over upstream retrieval and bounded bulk persistence. Source errors/timeouts persist a failed run; writes use a savepoint. Cancellation or unexpected internal/database failure rolls back the transaction and leaves prior evidence intact; it does not produce zero matches. A client disconnect is not a persistent queued job and may require retrying after the lock is released.

Successful cache TTL defaults to 24 hours (`SECOP_CACHE_HOURS`). GET never queries Socrata; repeat visits reuse stored evidence. Expired successes return `stale` until the user refreshes. A failed refresh preserves the last successful snapshot, visibly stale, with its original successful timestamp and the failed attempt/error separately exposed. No prior success plus a source outage returns `source_unavailable`; schema/safety failures return `failed`. `completed_no_matches` only means **no verified contracts in this dataset/query scope**, not no government business anywhere.

Refresh uses existing production rate controls, a database-backed per-company cooldown even in development, same-origin browser validation, empty-body enforcement, and the fixed official upstream host. Production already requires rate limiting and a single server worker. No upstream token reaches the browser. Logging contains safe event/error classes, not NITs or raw records. An optional existing `SOCRATA_APP_TOKEN`, HTTP timeouts, bounded retries and `Retry-After` behavior are shared with Phase 1; long requested waits fail safely instead of retrying early.

## API

All endpoints use versioned Pydantic response schemas and existing structured error responses:

- `GET /api/v1/companies/{company_id}/screening/secop`: cached outcome, identity, summary, freshness, source metadata, warnings and latest attempted status.
- `POST /api/v1/companies/{company_id}/screening/secop/refresh`: synchronous, empty body; returns result, or 409 for concurrent work / 429 for cooldown or rate limits. Browser callers must be same-origin.
- `GET /api/v1/companies/{company_id}/screening/secop/contracts`: `page` (1–10,000), `page_size` (1–50), normalized `status` (backward-compatible), exact reported `raw_status` (used by the interface), exact `entity`, `year` (signature, 1990–2100), `missing_signature_date=true` (only contracts without an available signature date; cannot be combined with `year`), exact `modality`, literal text `q`, `sort=date|value`, `direction=asc|desc`, optional successful `run_id`. Stable contract-ID tiebreaker and nulls last.
- `GET /api/v1/companies/{company_id}/screening/secop/contracts/{contract_id}`: normalized verified evidence and source link, optional `run_id`.

Source links use the exact published HTTPS URL only on `community.secop.gov.co` under `/Public/`, labeled **Proceso oficial SECOP II**. Otherwise the official dataset is linked and labeled as such. No contract URL is constructed.

## Running and verification

```sh
make migrate
make backend
make frontend
# Find a company, open Screening, then Consultar SECOP.
make test
make lint
make build
# Requires Docker and a disposable database; fixture runs upgrade/downgrade/re-upgrade/check.
make test-db
# Or supply your own DISPOSABLE PostgreSQL database (test fixtures truncate tables):
cd backend
TEST_DATABASE_URL=postgresql+asyncpg://cci:cci@localhost:5433/cci_test .venv/bin/pytest -m postgres
# From repository root: optional live, read-only, no database, at most 200 source rows:
backend/.venv/bin/python scripts/secop_smoke.py --nit 901449437
```

Automated tests use synthetic records and mocked HTTP. They cover exact supplier identity/DV/group exclusions, buyer-versus-supplier separation, duplicates/conflicts, decimals/currencies/dates, upstream count/paging/schema/drift/cap failures, unsafe links, API filters/details/ownership, migration/idempotency/cooldown/concurrency/rollback, frontend loading/failures/empty/stale states and snapshot pagination/details. Live smoke checks intentionally do not print source rows or credentials.

The implementation was validated against an isolated PostgreSQL 17.12 instance built and run under `/tmp`, with no system service. The database suite executed actual upgrade/downgrade/re-upgrade and Alembic schema-diff checks, Phase 1/2 regressions, SECOP persistence, cache/failure isolation, concurrent refresh rejection and transactional rollback. Frontend tests, lint/type checks, production builds, bounded live connector validation and desktop/mobile/tablet browser checks also passed. Final automated validation after the COP and nine-/ten-digit matching updates: all 293 backend tests passed together with PostgreSQL and `RUN_BROWSER_TESTS=1`. All 96 frontend tests passed, including large-portfolio alerts, highlighted summary metrics, sort direction toggling and five-contract pagination. Run the migration against your application database before using the new routes; no existing application database was modified during testing.

## Extension boundary

A future connector can reuse the company/source run history, atomic successful snapshot, exact identity evidence links, stale-success fallback and independent source status pattern. Add a separate adapter, verified matching rules, source ID, schema and source-specific UI component; expose it through a source selector in Screening. Do not reinterpret the SECOP outcome as an overall background-check result. Future SECOP I, SIC, Contraloría and regulatory connectors require their own validation and authorization; none is implemented here.

## Interface previews

The summary appears in the right half of the screening header on desktop and stacks below it on mobile. It contains the four metric cards in a 2×2 grid, with no synthesized paragraph. Estado, entidad and modalidad display in uppercase in both interface languages, including filters; source evidence and exact API filter parameters retain their original spelling. Filter choices and the status distribution are alphabetical. Monetary sections put a verified common currency in their heading/column and omit repeated per-value units; mixed currencies retain explicit codes. KPI values fit one line without rounding. The contract table uses five rows per page, an adjacent direction-toggle button beside the sort dropdown, sticky headers within its scroll container, and the same range-based pagination as Capital Markets. The year filter starts with `Sin fecha de firma`, which queries missing signature dates. Zero-valued missing-currency and invalid-value counters are omitted from the compact metrics note. Methodology is collapsed by default.

Screenshots use **synthetic test data**, not actual findings about a company. Browser verification covered a desktop viewport, tablet (768px), mobile (390px), contract detail opening/closing, browser errors and page overflow.

![Desktop Screening with synthetic data](screenshots/secop-desktop.png)

[Mobile preview](screenshots/secop-390.png) · [Tablet preview](screenshots/secop-768.png)
