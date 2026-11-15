# Capital-markets source discovery — 2026-11-14

## Access assessment and selected mechanisms

The existing application was inspected and its baseline executed: **92 backend tests against
PostgreSQL and 37 frontend tests passed**. Phase 2 extends its UUID companies, NIT/name
normalization, private SourceRecord audit storage, DataSource catalog, HTTPX, Alembic, and Query UI.
It does not replace RUES or infer legal form from securities data.

The selected issuer mechanism is an **administrative import of the official SFC XLSX download**.
The issuer portal is a JavaScript application. No documented public issuer API was established;
its application-internal endpoints are not used as a supported API. A public export button is a
reproducible human access mechanism, not evidence that an internal endpoint is an unrestricted API.
Securities use the observed public issuer-specific HTML report, one explicitly selected issuer per
command. Its report schema is validated; it is not advertised as an official API contract.
BVC corroboration remains unavailable pending an authorized reproducible source.

## SFC issuer directory

- Institution: Superintendencia Financiera de Colombia (SFC), SIMEV / RNVE.
- Public directory: <https://www.superfinanciera.gov.co/SIMEV2/rnve/emisoresinscritosvigentes>.
- SFC explanation: <https://www.superfinanciera.gov.co/publicaciones/10115778/national-registry-of-securities-and-issuers-rnve-in-spanish/>.
- Download: **DESCARGAR EMISORES → REPORTE EXCEL**, observed filename `Emisores.xlsx`.
- A real download through that public button produced one XLSX sheet, `Emisores`, with **311 issuer
  rows**, matching the unfiltered displayed count of 311. Header placement follows introductory
  logo/blank/generation rows; the parser discovers the exact header within the first 20 rows.
- PDF and combined issuer/securities Excel/PDF controls were visible. Their formats were not
  validated. The combined download did not yield a validated artifact in this session and is not
  used by the implementation.
- Filtered-export semantics could **not** be established conclusively. Attempted name-filter
  interactions left the displayed count at 311; both captured issuer workbooks contained 311 rows.
  This does not establish whether exports follow an actually applied filter. Imports default to
  **incomplete coverage**. A complete-current import requires explicit operator confirmation of an
  unfiltered current directory and its displayed row count, checked against the parsed file.

### Verified XLSX columns

| Actual column | Handling |
|---|---|
| Reporte | Must be `EMISORES`; schema/row validation. |
| Tipo de entidad | Source regulatory entity type; three-digit representation. |
| Descripción tipo de entidad | Preserve source label; not an ownership classification. |
| Código de entidad | Source entity code; three-digit representation. |
| Nombre entidad | Issuer name, separate from RUES legal identity. |
| NIT | Original source identifier; explicit source-specific normalization policy below. |
| Direccion | Not copied into queryable source-record payloads or public APIs. |
| Ciudad | Not used to populate company geography. |
| Teléfono | Excluded from queryable/public payloads. |
| Correo electronico | Excluded from queryable/public payloads. |
| Página web | Not used for external fetching; excluded from queryable payloads. |
| Nivel de supervisión | Not interpreted as registration/listing status. |
| Organismo de supervisión | Not interpreted as ownership or a listing finding. |

The workbook **does not contain an issuer-registration status, RNVE registration date, cancellation
date, ticker, ISIN, securities, or official publication/update timestamp**. Active registration is
attributed to the current issuer-directory context explicitly recorded with the import. Cancelled
and historical context imports are supported but were only tested with synthetic reports; actual
cancelled-export compatibility has not been live verified. Absence from a later confirmed full
current snapshot makes previously observed active records historical, never automatically cancelled.

A displayed `Fecha y hora de generación` is parsed as report-generation/observation time in
`America/Bogota` and stored separately from retrieval. It is **not** represented as a publication
or issuer-update date. A future timestamp fails import. Publication/update fields remain null.

### NIT and special structures

The report includes concatenated DV values: Banco de Bogotá is reported as `8600029644`, while
its real RUES registration supplies NIT `860002964` with DV `4`. The source also contains extended
fund/trust identifiers, including compartment suffixes. These must not be truncated into parent NITs.

Default `--nit-format preserve` preserves bare digits and does not verify a corporate link from
that ambiguous formatting. For this verified export, an operator may explicitly choose
`--nit-format concatenated-dv`: splitting is allowed only for exactly ten ASCII digits with a valid
Colombian DV checksum. Original values are always retained. Nonconforming values are not chopped.
Types `092` (negocios fiduciarios), `095` (investment funds), and `141` (foreign financial entities)
are preserved and never automatically linked to corporate RUES records. All 141 non-special rows
in the observed export satisfied the ten-digit/checksum rule; the other 170 rows were preserved as
special structures. This is a report-specific opt-in rule, not a change to Phase 1 NIT normalization.

A unique eligible exact NIT may link one issuer to one cached registration. Shared NITs, duplicate
issuer identities, DV conflicts, name-only matches, or special identifiers require review. Names,
including cached RUES aliases, can suggest candidates but cannot verify a link. Partial NITs and
brand/subsidiary similarities are never accepted as verified identity. Local uniqueness is not a
claim that every RUES registration has been downloaded.

## SFC registered-securities reports

Public report route:

```text
https://www.superfinanciera.gov.co/ReportesInformacionRelevante/faces/B_simevRelevantes/G_valoresInscritos/repoValoresInscritos.xhtml?entidad=CODE&tipoEntidad=TYPE
```

`CODE` and `TYPE` are taken from that issuer's imported source record, never a global bank example.
Live checked examples:

- Banco de Bogotá: [entity 001, type 001](https://www.superfinanciera.gov.co/ReportesInformacionRelevante/faces/B_simevRelevantes/G_valoresInscritos/repoValoresInscritos.xhtml?entidad=001&tipoEntidad=001): **15 rows ingested**.
- Bancolombia: [entity 007, type 001](https://www.superfinanciera.gov.co/ReportesInformacionRelevante/faces/B_simevRelevantes/G_valoresInscritos/repoValoresInscritos.xhtml?entidad=007&tipoEntidad=001): **18 rows parsed during discovery**; not used as a global entity parameter.

The report is public HTML with an issuer heading, `Títulos vigentes al` timestamp, table headers,
and `Registros encontrados` count. The parser checks exact issuer name, required headers, row
count, and duplicate identities. Truncated/changed/login pages fail rather than yield a negative.
The timestamp is an observed report timestamp, not a certified publication timestamp.

| Actual column | Application meaning |
|---|---|
| Nombre del título | Security name and original prefix. |
| Código ANN | `ann_code`, **never** silently treated as ISIN or ticker. |
| No. Emisión | Issuance number; distinct issuances remain distinct. |
| Tipo Inscripción | Original registration type, retained in provenance. |
| Inscrito en | Reported registration venue; `RNVE` alone does not name an exchange. |
| Número de Acto Administrativo RNVE | Original administrative reference. |
| Inscrito RNVE Fecha | RNVE registration date when parseable. |
| Inscrito BVC Fecha | Reported BVC registration event, **not** current trading confirmation. |
| Monto Autorizado | Decimal amount, using the observed Colombian grouping/decimal format. |
| Moneda | Original currency code or null for source N/A; no invented currency. |
| Última Calificacion | Source-reported rating, not an independently current credit assessment. |

Original strings remain available in allowlisted instrument evidence. Missing, malformed, and
placeholder values are not turned into dates or amounts. Unnormalizable present values generate
review notes. Reports do not provide verified tickers/ISINs or delisting/current-trading evidence.
Old instrument observations are retained if later reports omit them and are marked as prior evidence.

Instrument conventions were verified at the official
[Ver códigos](https://www.superfinanciera.gov.co/ReportesInformacionRelevante/faces/C_otrosRelevantes/C_titulosInscritos/links/convencionesTitulos.xhtml)
page: AO ordinary equity; ADP preferred equity; AP other equity; BO/BGG/BGE/BOCEAS bonds; PC
commercial paper; ACE/CDT/CDAT/CAVC/BDPI/TCC other debt. TP is left unclassified because the generic
participation-title label does not by itself prove a collective-investment classification. Unknown
prefixes remain `other_or_unknown`. Convertible bonds are not reclassified as currently listed shares.

## BVC access assessment

- Official website: <https://www.bvc.com.co/>.
- Official local issuer-listing page investigated: <https://www.bvc.com.co/listado-de-emisores-mercado-local>.
- Both returned **HTTP 403** in this environment during discovery. No publicly documented,
  unrestricted, reproducible listings feed was confirmed.
- No CAPTCHA, access restriction, private endpoint, or contractual control was bypassed.
- `BvcUnavailable` implements the connector boundary with `requires_authorized_source`.
  Listing remains `unknown` and `equity_listed` remains null. SFC-reported BVC registration dates
  remain usable independently. This is an access limitation, not a negative listing finding.
- A future authorized feed must preserve instrument/issuer identifiers, observation time, current
  status semantics, and provenance before it can set `verified_listed`/`verified_delisted`.

## Provenance, storage, and limitations

Raw XLSX/HTML files are stored privately by SHA-256 outside Git. They may include contacts even
though only allowlisted business fields are copied into public/queryable records. Do not publish
that storage directory or backups. A content hash verifies stored bytes, **not** source authenticity
or a complete-directory assertion; operators must retain the download context and protect imports.
Reports retain the source institution's applicable terms; MIT applies to software, not a relicensing
of regulatory files. Retention/access policies remain deployment responsibilities.

No full issuer export, source report binary, personal-contact fixture, or fabricated listing database
is committed. Standard tests use synthetic workbooks/HTML. Only the explicit operator refresh/smoke
commands contact regulators; company-profile reads use local data.
