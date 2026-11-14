# Architecture and identity decisions

```mermaid
flowchart LR
    U[React / Router] --> Q[TanStack Query]
    Q --> A[FastAPI v1]
    A --> S[Company search service]
    S --> R[Deterministic resolution]
    S --> D[(PostgreSQL 16)]
    S --> RA[RUES adapter]
    RA --> H[SocrataClient / HTTPX pool]
    H --> O[Official SODA 2.x API]
    D --> P[Profiles / allowlisted provenance]
    P --> A
```

The transport owns fixed-host HTTP, timeouts, pooling, concurrency, bounded retries, size caps,
JSON collection validation, and safe retry logging. The RUES adapter owns verified column names,
controlled SoQL, metadata checks, source dates, and record mapping. Normalization owns deterministic
NIT/name rules. The service owns matching, transactions, caching, and profile assembly. Pydantic
schemas define the public contract. The frontend uses only that contract and never has a source token.

## Registration-scoped companies

NIT is an indexed business identifier, not a primary key or unique constraint. Every company has
a UUID and an internal `rues-c82u-588k:<Socrata :id>` identity key. In this phase the canonical profile
is deliberately scoped to **one registration row**, not an assertion that the registry describes one
uniquely reconciled legal entity. A shared NIT or name never causes an automatic merge. The profile
reports how many other *cached* registrations share the NIT; this is not a complete registry count.

`:id as upstream_id` was verified live. It identifies distinct rows even when a chamber/matrícula/NIT
combination is duplicated or missing. Source system IDs can change during publisher replacement;
future reconciliation must treat them as source identity, not an eternal business identifier. If `:id`
is missing, a hash-based identity is retained and matching is `unresolved`. A changed hash without
a system ID becomes a new unresolved profile. We do not guess a registration key from unrelated fields.

`CompanyAlias` preserves observed legal names (including previous names) with source attribution.
`SourceRecord` preserves complete source payloads in private JSONB. Its unique key is source +
external row ID + SHA-256 hash. Re-fetching identical content updates retrieval time rather than
creating redundant versions. Changed payloads create versions; `source_updated_at` stays separate
from retrieval and official dataset update timestamps. Raw historical data and aliases can contain
personal information: treat the database as restricted data, including backups.

Updates run in one database transaction. PostgreSQL conflict-safe inserts and per-company row locks
prevent concurrent duplicate company creation. Foreign keys preserve source/company relationships.
The application does not create tables on startup: Alembic owns schema lifecycle.

## Search and cache behavior

Each request performs one metadata check and one filtered source query; each has at most two retries
by default. Each page retrieves at most 51 rows (50 results + lookahead), has a bounded offset, and
uses `:id` ordering. A process-wide semaphore caps active upstream operations. No eager downloading,
API fan-out, or background ingestion occurs. User text is a quoted literal, never a SoQL expression.
User `%`/`_` wildcards are removed. Remote matching is a case-insensitive substring query that
removes literal spaces from the source name and whitespace from the query. It does not implement
accent-insensitive full-text search. Shorter distinctive names help.

Results are deterministically classified and ranked **within the current page**; we do not claim a
registry-wide ranking or a total count. Source updates can shift offset pages between requests.
All source candidates remain separate. An explicitly supplied conflicting/missing verification digit
produces `unresolved`, not an exact identifier match. Bare digit strings are never truncated to guess
a verification digit. Format validation does not certify an identifier's DIAN checksum or ownership.

If the source returns no current name matches, exact normalized names/observed aliases and
spacing-insensitive name/alias prefixes in the cache can recover previously consulted variants;
these results carry a cache warning and stale flag. On a source failure, NIT equality or normalized name/alias prefix queries can return cached results,
always explicitly stale. NIT and normalized-name indexes, plus PostgreSQL `text_pattern_ops` prefix
indexes and expression indexes on space-stripped normalized names support those bounded local
queries. Cache fallback does not claim full substring coverage.
A failed live request with no cache returns a structured 503, never a false empty result.

## Provenance and states

`FIELD_MAP` is the versioned mapping from API attributes to official column names, exposed alongside
allowlisted source fields. Profile attributes point to source fields and record UUIDs. States include
present, missing from this record, unavailable in this dataset, not checked, and malformed/ambiguous.
Source availability separately reports not-yet-checked, available, or failed-to-retrieve. Multiple
registrations sharing a NIT require manual review; no percentage confidence is invented.

Future financial attributes will need individual evidence versions, units, periods, and transformations.
Keep them in separate bounded-context tables/services rather than adding financial columns to Company.
Future connectors that screen datasets need not implement company search. No plugin framework is needed.

## Deployment boundary

Compose is a local development setup: a PostgreSQL volume, one-shot migration service, API, and Vite
frontend proxy. Ports bind to loopback. It is not a public production deployment. The frontend builds
to static assets; production requires a static host with SPA fallback and an `/api` reverse proxy,
HTTPS, authentication/access policies, request/rate limits, retention controls, and reviewed public-data
usage. Application errors are sanitized and access logs are disabled by the documented launch command.
Never enable query-string logging on a public reverse proxy: searches may contain personal identifiers.


Word-spacing tolerance uses a separate search-only comparison key. The original legal name,
stored normalized name, source records, NIT, and registration-scoped UUID identity are unchanged.
Space-insensitive full-name matches are `normalized_name`; substring matches are `partial_name`,
with explicit evidence. Different entities with colliding compact names remain distinct candidates.
Migration `a4e58b192f70` adds expression indexes for existing company/alias names without a backfill
or data rewrite. The source query remains one bounded request, not a fan-out of guessed word splits.
