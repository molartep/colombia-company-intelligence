# RUES source discovery and contract

Verified live on **2026-11-13** against the official source, before implementing the adapter.

- Dataset: [Personas Naturales, Personas Jurídicas y Entidades Sin Animo de Lucro](https://www.datos.gov.co/d/c82u-588k).
- Publisher attribution: **Confecámaras, Bogotá D.C.**
- Dataset ID: `c82u-588k`.
- Metadata: `https://www.datos.gov.co/api/views/c82u-588k.json`.
- SODA 2.x resource: `https://www.datos.gov.co/resource/c82u-588k.json`.
- Metadata license ID: `CC_40_BY_SA` (CC BY-SA 4.0). Software MIT licensing does not relicense the source data.
- Official row update timestamp: **2026-11-06 20:49:30 UTC** (`rowsUpdatedAt=1793998170`).
- Metadata modification timestamp: **2026-09-08 00:21:11 UTC** (`viewLastModified=1788826871`).
- Sanitized metadata snapshot: [`discovery/metadata.json`](discovery/metadata.json).

## What was actually checked

Discovery retrieved metadata, three arbitrary rows with `$limit=3`, two bounded non-natural-person
rows, and two bounded name matches. It verified `$where`, `upper(...) like`, `$order=:id`, and
`:id as upstream_id`. The actual implemented adapter subsequently passed a metadata check, an exact
NIT lookup, and a filtered name lookup, each limited to one row. No complete download or count was run.
Representative raw records are deliberately **not committed** because they include natural persons.
The test suite uses synthetic records; its schema fixture comes from the saved official metadata.

There are **36 exposed data columns, all typed `text`**. Socrata system `:id` is additional metadata,
explicitly selected as `upstream_id`, not a published business identifier. The table below reproduces
the complete discovered schema. Descriptions are available verbatim in the metadata snapshot.

| API field | API type | Meaning / application use |
|---|---|---|
| `codigo_camara` | `text` | Official chamber code; retained as a string. |
| `camara_comercio` | `text` | Chamber name, not a municipality. |
| `matricula` | `text` | Mercantile registration number; not globally unique. |
| `inscripcion_proponente` | `text` | Proponent registration; raw storage only. |
| `razon_social` | `text` | Legal name; original display name and normalized comparison. |
| `primer_apellido` | `text` | Personal surname; private raw storage only. |
| `segundo_apellido` | `text` | Personal surname; private raw storage only. |
| `primer_nombre` | `text` | Personal name; private raw storage only. |
| `segundo_nombre` | `text` | Personal name; private raw storage only. |
| `sigla` | `text` | Reported acronym; raw storage only; not assumed to be a separate legal entity. |
| `codigo_clase_identificacion` | `text` | Identification class code; raw storage only. |
| `clase_identificacion` | `text` | Identification class; raw storage only. |
| `numero_identificacion` | `text` | May be a citizen identifier; never substituted for NIT or exposed. |
| `nit` | `text` | Nullable tax identifier; normalized as a string. |
| `digito_verificacion` | `text` | Verification digit, separately nullable. |
| `cod_ciiu_act_econ_pri` | `text` | Primary CIIU code; leading zeroes preserved, no invented description. |
| `cod_ciiu_act_econ_sec` | `text` | Secondary CIIU code; retained in allowlisted source fields. |
| `ciiu3` | `text` | Additional CIIU code; retained in allowlisted source fields. |
| `ciiu4` | `text` | Additional CIIU code; retained in allowlisted source fields. |
| `fecha_matricula` | `text` | Registration date; source string. |
| `fecha_renovacion` | `text` | Last renewal date; source string. |
| `ultimo_ano_renovado` | `text` | Last renewed year; source string. |
| `fecha_vigencia` | `text` | Validity date; raw storage only; may be a sentinel. |
| `fecha_cancelacion` | `text` | Cancellation date; source string. |
| `codigo_tipo_sociedad` | `text` | Society type code; private raw storage only. |
| `tipo_sociedad` | `text` | Society type; not used as a substitute for legal organization. |
| `codigo_organizacion_juridica` | `text` | Legal organization code; raw storage only. |
| `organizacion_juridica` | `text` | Legal organization description → legal_form. |
| `codigo_categoria_matricula` | `text` | Registration category code; raw storage only. |
| `categoria_matricula` | `text` | Registration category; raw storage only. |
| `codigo_estado_matricula` | `text` | Registration status code; raw storage only. |
| `estado_matricula` | `text` | Registration status description. |
| `clase_identificacion_rl` | `text` | Representative identification class; excluded from public API. |
| `num_identificacion_representante_legal` | `text` | Representative personal identifier; excluded from public API. |
| `representante_legal` | `text` | Representative name; excluded from public API. |
| `fecha_actualizacion` | `text` | Record update timestamp; source_updated_at when parseable. |

## Availability and mapping limitations

NIT and DV are absent from some records. A citizen identification number is **not** a fallback NIT.
The dataset covers natural persons, legal entities, and nonprofit entities, including cancelled
registrations. A matrícula's status is not proof of entity-wide legal standing or current operations.

**Department and municipality are not in this schema.** Chamber names are not geographic addresses.
No official geographic or CIIU description lookup has been integrated. Codes are displayed verbatim.
The source has no verified ownership, listing, financial, transaction, procurement, regulatory, or
fiscal screening attributes. Those are **not checked**, never verified negatives.

Date columns are text, not typed dates. Observed date strings include `YYYYMMDD`, `0`, and sentinel
`99991231`; missing/zero values must not be interpreted as actual events. Registration dates remain
source strings. `fecha_actualizacion` samples use `YYYY/MM/DD HH:MM:SS.fraction` without timezone;
the adapter explicitly assumes `America/Bogota`, truncates fractions to microseconds, and converts
to UTC. This timezone is an application interpretation, **not a timezone certified by metadata**.
Unparseable update timestamps remain null; the original text remains available in source fields.

NIT normalization validates display syntax, 5–15 digits, and explicit optional `-DV`; it preserves
leading zeroes and does not guess that a bare trailing digit is a DV. It does not mathematically
certify checksum validity. Source DV conflicts produce an unresolved search match.

Case-insensitive substring queries are verified; accent-insensitive remote matching is not claimed.
Normalization handles comparison/ranking and exact cached name/alias variants. Retry a shorter
source-spelled name when no candidate appears. Search is capped at 100 pages, 50 results per page;
ranking applies only to returned candidates on that page. Offset pagination is not a snapshot.

The source's system row IDs were verified, but their permanence across full publisher replacement
is not guaranteed. Different records sharing a NIT remain different company profiles. Missing system
IDs use a hash identity with `unresolved` matching. Historical source versions are retained privately.

## Query contract and live validation

The application uses SODA **2.x GET query parameters only**, never SODA 3 POST request syntax:

```text
$select=*, :id as upstream_id
$where=nit = '890001255'
$order=:id
$limit=1
$offset=0
```

Name queries use `upper(razon_social) like '%SAFE LITERAL%'` with escaped single quotes and controlled
wildcards. Callers cannot supply raw SoQL, dataset IDs, or upstream URLs. HTTPX uses a fixed official
host, configurable timeout, pooled connections, a global concurrency cap, and an optional server-side
`X-App-Token`. There is no frontend token or proxy to arbitrary upstream paths.

```sh
# From repository root, after installing backend dependencies:
make smoke
# Equivalent: backend/.venv/bin/python scripts/live_smoke.py
```

The smoke command performs three bounded requests, prints counts/schema status only, writes no raw
records, and needs no database or paid service. It fails on connectivity/contract errors. A valid empty
response is explicitly reported and may mean the chosen smoke-test company changed in the dataset.

A metadata/schema failure is an integration failure, not a no-match outcome. The normal test suite
never calls this service. Re-run discovery and review mapping before accepting new field types/names.

## Public-data usage and privacy

The registry includes natural persons operating businesses. Public accessibility does not establish
unrestricted redistribution rights or remove privacy obligations. The identity UI necessarily displays
a legal name/NIT when the source supplies it. The public source endpoint returns only allowlisted
registration fields and excludes citizen numbers, separate personal-name fields, and representative
details. Raw JSONB still contains them for auditability and must remain private.

Local Compose ports are loopback-only; do not publish the database. Restrict database/backups to
operators, avoid query/payload logging, define an appropriate retention/deletion process, and review
lawful usage before public deployment. No bulk export, scraping, indexing endpoint, or public raw-data
API is provided. Cached record versions currently have no automatic expiry: retention controls are a
prerequisite for sustained public operation. The footer attributes Confecámaras and the metadata's
CC BY-SA license; adapted data redistribution may have attribution/share-alike obligations separate
from the MIT software license. Do not treat this application as a certified registry extract or a
substitute for authoritative due-diligence/legal verification.
