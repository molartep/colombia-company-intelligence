# Advanced search filters

Implemented and verified against the official RUES SODA 2.x resource on **2026-11-14**.

Search still requires a name or NIT. Expand **Advanced filters**, select values, then submit
**Search** (or Enter). Editing filters does not execute a company search. Fixed options load once
from the application's versioned catalog when the section opens. Multiple values within one
filter use OR; different filters use AND. Conditions apply at RUES before relevance ordering and
LIMIT/OFFSET, so pagination represents the filtered result set, rather than a filtered current page.

The header's **Parameters** page explains each fixed filter and shows the actual source codes,
verbatim reported meanings, source URL, verification time, and dataset update time. Help buttons
show descriptions on hover or keyboard focus; tapping/focusing them also exposes help on mobile.

## API

`GET /api/v1/companies` retains `q`, `page`, and `page_size` and accepts these optional parameters:

| Parameter | Values / meaning |
|---|---|
| `status` | Repeated reported registration-status codes; matches `codigo_estado_matricula`. |
| `chamber` | Repeated chamber codes; matches `codigo_camara`, not company geography. |
| `organization` | Repeated legal-organization codes; matches `codigo_organizacion_juridica`. |
| `category` | Repeated registration-category codes; matches `codigo_categoria_matricula`. |
| `ciiu` | One code, preserving leading zeroes. Exact requires four ASCII digits; prefix accepts one to four. |
| `ciiu_match` | `exact` (default) or `prefix`. |
| `ciiu_scope` | `primary` (default) or `any`; any checks primary, secondary, third, and fourth reported activities. |
| `registration_from`, `registration_to` | Inclusive ISO calendar dates, `YYYY-MM-DD`. Either endpoint may be omitted. |
| `renewal_from`, `renewal_to` | Inclusive ISO calendar dates, with either endpoint optional. |
| `renewed_year` | Four-digit year, 1000–9998; filters `ultimo_ano_renovado`, independently of renewal date. |
| `renewed_year_mode` | `exact` (default) or `minimum` (selected year and later). |

```sh
curl --get http://127.0.0.1:8000/api/v1/companies \
  --data-urlencode 'q=Palomma' \
  --data 'status=01' --data 'status=03' \
  --data 'organization=16' --data 'category=01' \
  --data 'ciiu=62' --data 'ciiu_match=prefix' --data 'ciiu_scope=any' \
  --data 'registration_from=2020-01-01' \
  --data 'renewed_year=2024' --data 'renewed_year_mode=minimum'
```

`GET /api/v1/parameters` returns the versioned catalog without database or upstream requests.
Fixed codes are validated against this catalog. Nonpersonal registration filter codes and the
registration category are also available in allowlisted source-record provenance. Unknown codes, malformed dates, reversed ranges,
unsupported modes, arbitrary SoQL, and invalid CIIU values return the consistent 422 error schema.
The bounded query-string cap is 8 KiB to accommodate multiple fixed-value selections. Selection
arrays are bounded and deduplicated. Source hosts, field names, operators, and wildcards remain
controlled by the backend; no user expressions are accepted.

## Dates and missing data

RUES date and year fields are text. A range includes only valid eight-digit Gregorian calendar
dates within the supplied endpoints. Text-only validation checks digits, month lengths and leap
years, including century rules, without casting malformed strings into dates. It excludes blank,
missing, zero, impossible, and year-9999 placeholder values. No range means this exclusion is not
applied. Consequently a filtered result is not a finding that excluded registrations never existed.

Year filtering excludes malformed, zero, and year-9999 placeholders. No checksum, financial,
listing, geographic, or business-standing conclusion is inferred from any filter.

## Verified fixed options

A bounded discovery used four server-side aggregations, each capped at 501 code/label pairs and
explicitly checked for truncation. It retrieved no company/person records. The checked-in catalog
contains **15 status options** (including a missing-code choice), **58 chambers**, **53 legal
organizations**, and **2 registration categories**. It contains no record counts or personal data.

These are observed values, not a separately certified exhaustive legal taxonomy. Notable distinctions:

- Status `01` is reported as `ACTIVA`; `03` as `CANCELADA`; `07` and `09` retain their distinct
  transfer-related labels.
- `04` is reported as `NO COMPETENCIA DE LA CAMARA`. An anomalous unpadded `4` has no reported
  description and is **not** silently mapped to `04`.
- Legal organization `00` has no reported description. Organization `16` is reported as
  `SOCIEDADES POR ACCIONES SIMPLIFICADAS SAS`.
- Category `00` is reported as `PERSONA NATURAL`; `01` as
  `SOCIEDAD ó PERSONA JURIDICA PRINCIPAL ó ESAL`.
- `__missing__` is an application selection value for a missing/blank code, not a RUES code.
  It is offered only for groups in which missing codes were observed.

The source-provided description is the code meaning shown to users; broader legal interpretations
have not been added. CIIU has code/prefix entry rather than an invented classification-description
catalog. No authoritative CIIU description lookup has been integrated.

Catalog: `backend/app/integrations/rues/data/parameters.json`. It is bundled with the backend wheel
and Docker image. It can lag publisher changes; verification and official dataset timestamps are
shown separately. Refresh explicitly, review the diff, and restart the backend:

```sh
SOCRATA_TIMEOUT=60 backend/.venv/bin/python scripts/refresh_parameters.py
# or: SOCRATA_TIMEOUT=60 make refresh-parameters
```

Refresh uses one metadata request plus four bounded, sequential aggregate requests, with bounded
retries and optional server-side app-token authentication. It refuses truncated/malformed responses
and conflicting labels for the same code. The catalog is written only after all queries succeed.
Normal searches never execute aggregation queries or download a complete dataset. Parameters is
read-only; source-backed option meanings are updated through reviewed catalog changes.

## Pagination and caches

Filter values are preserved in the URL, Next/Previous links, and the profile's return link.
Submitting changed filters resets page to 1. Frontend cache keys include all applied filter values
in a canonical order; filtered and unfiltered pages cannot reuse each other's results. Clear filters
only edits the form until Search is submitted. Explicit submission refreshes the selected search.

Source-failure and empty-source normalized-name fallbacks apply the same code, CIIU, calendar-date,
and year predicates to the latest cached source record **before** local offset/limit. They remain
explicitly stale and have only cached coverage and page-local ranking. If a source failure has no
cached records satisfying every filter, the error is returned rather than unfiltered results.

## Socrata references

Implementation follows the documented SODA GET conventions:
[WHERE and boolean operators](https://dev.socrata.com/docs/queries/where.html),
[GROUP BY](https://dev.socrata.com/docs/queries/group.html),
[LIMIT](https://dev.socrata.com/docs/queries/limit.html), and
[SoQL functions](https://dev.socrata.com/docs/functions/).
Text equality, IN, LIKE, comparisons, substring, trim, and replace were exercised on the live
resource. `substring` uses one-based indexing. No SODA 3 POST syntax or ingestion-only transform
functions are used. Live validation confirmed combined code/date filters, exact/any-prefix CIIU,
and exact/minimum renewed year using bounded Palomma queries and actual reported values.
