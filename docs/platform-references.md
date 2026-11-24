# Platform References

The former Advanced page is now **Platform References** / **Referencias de la plataforma**.
Its URL is `/references`; the previous `/advanced` URL redirects there. It describes all three implemented paths:
RUES company registration, Capital Markets, and Government Contracts through SECOP II.

The architecture diagram shows the frontend, FastAPI, private storage and source connectors.
The technical flow diagram separates the three source workflows. Seven expandable technical
steps explain matching, persistence, import, quotes, government contracts and runtime controls;
all start collapsed. The former Scope and limits card was removed during the earlier redesign. A current capability
matrix now distinguishes readiness from local database counts. Diagrams use semantic
HTML and small inline SVG arrows, localized labels and responsive layouts; no diagram dependency
or remote renderer is needed.

The [capability matrix](capabilities.md) is the canonical scope review. The rendered matrix uses
the same readiness categories, including partial RNVE coverage, experimental quotes, implemented
Government Contracts, USD presentation/exports and planned financial statements/additional screening.
No rate is retrieved by visiting References; it is opt-in on company profiles.

## Recorded data readiness

`GET /api/v1/platform` reads local database history. It does not probe upstream sources or run
screenings. The additional `secop` object contains the latest global screening status, last attempt,
last successful completion, source update time from that success, configured cache hours and row
cap. No company identifier or supplier document number is exposed here. These are global history
observations, not a claim of complete government contracting coverage or fresh company results.
The row cap remains 5,000 by default; cap failures retain the existing alert and no-partial-totals
behavior. No database migration is needed for these additional diagnostics.

Metric cards keep counts on one line and provide keyboard-accessible information tooltips:

| Key | Count |
| --- | --- |
| `registrations` | Stored RUES registration rows; several may belong to a company. |
| `source_records` | Stored RUES/SECOP evidence versions, including historical versions. |
| `issuers` | Imported RNVE issuer records. |
| `instruments` | Stored security instrument records. |
| `snapshots` | Capital Markets retrieval snapshots, including failed attempts. |
| `verified_links` | Verified issuer-to-company identity links. |
| `screening_runs` | SECOP checks, including failures and repeated checks. |
| `secop_contracts` | Distinct SECOP contract IDs across all stored evidence versions. |

The SECOP contract metric is a historical global count, not the count for a selected company's
latest screening. Repeated runs and changed evidence versions cannot inflate it.

## Spanish technical glossary

These terms are retained in English in application-controlled technical copy:

| Term | Meaning in this platform |
| --- | --- |
| **snapshot / snapshots** | A recorded retrieval observation/version and its metadata. |
| **cache / caches** | Stored results reused according to their freshness policy. |
| **fallback** | An alternate source or use of earlier evidence after a source fails. |
| **parser** | Code that validates and extracts fields from a source document. |
| **runtime** | The application's execution environment and operational boundaries. |

Spanish explanations remain localized. “Copias de respaldo” still describes backups; “registros
de respaldo” still describes supporting evidence. Neither is a technical fallback. Source records,
external classifications and source text remain unchanged regardless of this glossary.

## Verification

Frontend tests verify the renamed page, EN/ES copy, technical glossary, tooltip definitions,
SECOP readiness, diagrams and collapsed workflows. The PostgreSQL regression test verifies
empty readiness, successful runs, distinct contract IDs across versions, and preservation of
last-success metadata after failure. Browser checks cover both languages, single-line metric
counts, focused tooltips, diagrams, and desktop/tablet/mobile widths.
