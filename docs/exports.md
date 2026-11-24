# Research exports (schema 1.0)

`GET /api/v1/companies/{UUID}/exports/research?format=csv|json`
and `GET /api/v1/companies/{UUID}/exports/contracts?format=csv|json`.
No source refresh is triggered; current stored evidence is exported. Both routes use existing
request limits, company identity checks and sanitized API errors. Responses use attachment filenames
and `Cache-Control: no-store`. Bounds: **1,000 rows and 5 MiB UTF-8**, including CSV metadata.
Requests exceeding either bound fail with 413 and no truncated download. Research exports with
more data cannot currently be split; contract users can narrow filters. This is an analysis export,
not a bulk source archive or a grant of third-party redistribution rights.

## Interface

A single pale-green, one-line export bar appears above the company title. Select **Company research**
or **Filtered contracts** (available while a successful contract snapshot is displayed), then open
**Export** and choose CSV or JSON. The contract scope follows the current table filters across all
pages, defaults on while viewing available contract results, and is disabled during result updates
or table failure. Company research remains selectable independently. Full limits, source/completeness
warnings and scope details are available through the information tooltip. The dropdown supports
native keyboard navigation, Escape with focus return and outside-click dismissal.

## Envelope and row schema

JSON has `schema_version`, `scope`, `exported_at` (UTC), `company` (UUID, NIT, DV, original legal
name/form), `screening`, applied `filters`, `presentation_rate`, `warnings`, `row_limit`,
`truncated=false`, and `rows`. Contracts add `filtered_total` and `snapshot_run_id`. Research adds
`capital_markets` (RNVE finding, unassessed ownership, securities availability, source metadata,
stale status and limitations). Unavailable fields remain null, not zero or inferred negative facts.

`screening` carries outcome, last successful/attempt timestamps, source URL/ID/update date, cache
age/TTL, run identity/status, summary and warnings. Internal query metadata is excluded. Summary
is the **whole successful portfolio**, not the filtered row total. `filters` describes row selection.

CSV is UTF-8 with BOM, CRLF records, header row and RFC-style quote/comma/newline escaping. Columns
are the union of row fields, with `metadata_json` containing the envelope without `rows` repeated
on each row. Nested values use JSON text. An empty successful result includes one metadata-only
CSV record; it is not a contract. JSON `rows` is empty. Data dictionaries are not flattened into
locale-dependent labels. Column names/schema keys stay invariant between EN/ES.

### Contracts

Each row is the public `ContractView`: contract/process/reference IDs; original and normalized
supplier NIT and document type; source row identifier, URL/link kind, evidence ID and retrieval/
source-update dates; exact match method/status; buyer/NIT; original description, raw status, type,
modality, geography and dates; original `value`, `currency`, `currency_basis`; normalized `status`.
Optional `presentation_usd` is a **separate string**, only for non-null COP values. Decimal amounts
remain JSON strings, preserving precision and scale; raw external labels are never translated or
uppercased during export. Dates use API ISO representations.

All table filters apply across **every matching page**, not only the visible five contracts:
`q`, `raw_status`, normalized `status`, `entity`, signature `year` or `missing_signature_date`,
`modality`, `sort=date|value`, `direction=asc|desc`. The `run_id` supplied by the UI must match the
latest available successful snapshot; a superseded run returns 409 so users reload. Rows are pinned
to that successful snapshot, with existing company/source/NIT ownership validation and stable sort.
Filters operate on original values. Conversion never affects selection or ordering.

### Company research

Rows have `record_type`: `registration` (public identity, registration, attribute availability,
freshness and source metadata); `evidence` (source-version ID, source row ID/link and retrieval date);
`issuer` (identity, registration, source/snapshot and match metadata); `security` (identifiers,
original category/type, registration venue/status, authorized amount/currency, source evidence,
freshness and quality notes); `quote` (provider/identity link, original reported price/currency,
price kind/date, retrieval, source and stale status). Securities are retrieved across the local
verified issuer set, independently of the displayed first page. Issuer candidates retain their
match status. Contact/administration details, raw payloads, personnel, bank accounts, internal file
paths, credentials, and arbitrary source-value dictionaries are excluded by explicit projections.
The latest **50 source evidence versions** are included; older history exclusion produces a warning.
The export does not include full contracts; use the filtered contract export for those rows.

## Stale, unavailable and capped evidence

Stale stored evidence is exportable with its original successful date, explicit state and warnings;
exporting does not make it fresh. Research remains exportable with absent-source states. Contract
exports without a successful snapshot return 409, including an unavailable or capped first query.
A completed zero-match snapshot exports a valid empty result. A failed/capped refresh with an earlier
success exports only that previous snapshot, preserving the failure/cap warning; no partial new
portfolio or partial total is invented. The independent SECOP cap is 5,000 source rows by default,
not an export allowance. Warnings and completeness must accompany downstream analysis.

## Currency and spreadsheet safety

Optional parameters: `fx_mode=cop|reference|manual`, `manual_rate` (positive COP per USD decimal),
`rate_date` (required for manual API requests; the UI supplies the Colombia date of entry
automatically, without a date input). Default `cop` produces no converted fields. Reference conversion
requires a current successfully validated rate; stale/unavailable reference requests fail rather
than exporting an unexplained conversion. [Provider assessment and rounding](currency-presentation.md).

CSV cells beginning with formula markers `=`, `+`, `-`, `@` after whitespace, or leading tab/CR/LF,
are prefixed with an apostrophe. This intentionally changes CSV text for spreadsheet safety;
JSON preserves the original external value exactly. Spreadsheet importers can still reinterpret
long numeric strings/leading zeros; import identifier and decimal columns as **text**, or use JSON
for lossless machine analysis. Quoting alone cannot prevent formula injection.
