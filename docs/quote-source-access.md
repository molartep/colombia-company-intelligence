# Quote source access assessment — 2026-11-15

## Public access tested

| Source / method | Observed result | Integration decision |
|---|---|---|
| BVC detail, root and canonical non-www URL using HTTPX | HTTP 403 CloudFront | Preserve the failure; no fabricated price. |
| BVC web fetch | HTTP 403 | Not usable here. |
| BVC normal bundled Chromium 159 | HTTP 403 | No challenge bypass attempted. |
| BVC normal installed Chrome 157 | HTTP 403 page | No successful standard browser path found here. |
| Grupo Aval daily quote page using HTTPX and normal Chromium | HTTP 200; main stock quote table had headers but no populated rows | Reachable page, presently unusable quote feed. |
| La República Ecopetrol using HTTPX | HTTP 403 | Use the verified normal-browser path instead. |
| La República normal Chromium | HTTP 200; dated quote and technical-sheet legal name/ticker | Activated as a labeled secondary source after exact identity validation. |

This does not prove BVC is inaccessible from every network/session or in the future. It records the
ordinary public access methods tested here. No proxies, credential extraction, CAPTCHA solving,
fingerprint spoofing or private endpoints were used.

Sources: [BVC Ecopetrol](https://www.bvc.com.co/renta-variable-mercado-local/ecopetrol?tab=resumen),
[Grupo Aval daily quotes](https://www.grupoaval.com/wps/portal/grupo-aval/aval/portal-financiero/renta-variable/acciones-bolsa-colombia/cotizaciones-dia),
[La República Ecopetrol](https://www.larepublica.co/indicadores-economicos/movimiento-accionario/ecopetrol).

## Grupo Aval feasibility

The page explicitly states a 20-minute delay and exposes Hora, Acción, Último Precio, Variación,
N° Acciones and Volumen columns. Both actual HTTP/rendered responses had no stock rows in that
main table. Header ticker widgets and index values were not substituted for stock observations.
No eligible quote row supplied NIT, ANN or an exact legal company name. The declared refresh timer
was roughly 300,000,000 milliseconds. Re-evaluate the rows/identifiers if this feed resumes; this
assessment does not establish permanent unavailability. It is not activated as an identity-verified
fallback under the requested matching rules.

## La República fields verified live

The stock quote block exposes main price, variation, FECHA, CANTIDAD and VOLUMEN. The separate
technical sheet supplies legal name, Nemotécnico and a secondary assertion about BVC listing.
NIT and ANN were absent. Contact/management information is not extracted or redistributed.

Actual observed Ecopetrol values: legal name `ECOPETROL S A`, ticker `ECOPETROL`, price `$ 2.545`,
quote timestamp `13/11/2026 - 03:42:12 PM`, variation `+1,19%`. These were retrieved from the public
page, not inserted as fixtures. Colombian numeric separators parse to Decimal 2545; the timestamp
uses America/Bogota (-05:00). A November 15 retrieval does not make it a November 15 market quote.
The UI displays source quote date and retrieval time separately. The observed La República quote
block states no numerical delay; Grupo Aval's 20-minute delay is not attributed to this source.

## Exact matching rules

1. Reject conflicting reported NIT or ANN even if the name matches.
2. Prefer exact normalized NIT, then exact reported ANN, then exact legal name.
3. Legal-name comparison only normalizes Unicode presentation, case and whitespace. Punctuation,
   diacritics, suffixes and words remain intact. Tickers and URL slugs never establish identity.
4. More than one SFC ordinary-share record blocks all quote retrieval and cached display, even
   if rows share an ANN or are on another market. Automatic and manual refresh follow this rule.
   With one record, company-only NIT/name matches require one eligible ANN; explicit preferred shares/PF tickers cannot become
   common equity. The issuer/company relationship must already be verified.
5. Revalidate cached identity evidence against today's company record before displaying it.

Ecopetrol's technical-sheet name exactly matched the RUES name `ECOPETROL S A`. The displayed ANN
is linked from RNVE; La República did not publish it. The API records match type/value and publisher.
Secondary-source quotes do not set an authoritative verified BVC listing state.

## Retrieval, cache, provenance and coverage

The BVC connector remains primary. If it has no fresh matched quote, a configured La República
page can supply a separately attributed observation. Sources have independent snapshots, errors,
15-minute quote caches and per-source manual refresh. The initial page catalog covers the supplied
Ecopetrol URL. More official publisher pages can be configured using `LA_REPUBLICA_PAGE_URLS`
(JSON ANN-to-URL routing hints); their responses still must pass identity validation. No unbounded
stock-page crawl is performed.

Normal Chromium navigation uses isolated contexts, two concurrent slots and a total deadline.
Raw HTML artifacts are private and SHA-256 identified. Public payloads contain only quote/identity
evidence, not contact/representative details. Failed refresh preserves earlier matched observations
as stale; an identity change can invalidate a cached name match. No exact match produces a red
alert inside the BVC card. Source/identity alerts are grouped in a collapsed panel and the old
summary banner is removed. `refresh=true&refresh_source=la_republica_quotes` targets only that source.
Publisher terms continue to apply to market data; the software license does not relicense it.


### Registration indicator and former names

The green **Registrado** badge means at least one RNVE security has category `common_equity`
and trimmed, case-insensitive market `BVC`. Its tooltip explains that this is a registration
finding, independent of table filters and pagination; it does not verify current trading.
The profile exposes `common_equity_record_count` over all ordinary-share records, without
filtering by market or requiring an ANN. More than one triggers a collapsed alert and disables
quote refresh buttons. Both quote services independently enforce the guard before any retrieval.

When the single ordinary-share record is BVC-registered, explicit former legal names from
`AO <name> - ANTES <former name>` titles join the exact-name candidates. These names are scoped
to that instrument and retain punctuation, accents and legal suffixes. Conflicting NIT/ANN
still reject the match. Former names are revalidated for cached observations too.

Celsia's verified locator is the public [La República quote page](https://www.larepublica.co/indicadores-economicos/movimiento-accionario/celsia),
routed from RNVE ANN `COT60PAAO005`. Its technical sheet reports `CELSIA S.A. E.S.P.`, exactly
matching the former name in `AO CELSIA S.A. - ANTES CELSIA S.A. E.S.P.`. The page uses uppercase
`NEMOTÉCNICO`; browser readiness is case-insensitive. URLs are routing hints, never identity evidence.


## Registered ordinary-share fallback (Terpel case)

The sequence is BVC public page → La República public page → SFC public daily-price report.
Each step stops network retrieval when an earlier source has a fresh exact match. Cached
observations remain revalidated against current identity. Multiple ordinary-share records block
all providers, including manual refresh. Only BVC-registered ordinary-share instruments qualify
for the SFC fallback. There is no match by brand, URL slug, ticker or approximate legal name.

### Sources evaluated

| Source | Observed interface and identity | Integration decision |
| --- | --- | --- |
| BVC | Public summary page; requires a verified locator and actual reported code. Prior ordinary public requests were blocked. | Keep first in sequence. No locator means **not configured**, not a claimed failed request. |
| La República Terpel | [Public page](https://www.larepublica.co/indicadores-economicos/movimiento-accionario/terpel) has a quote but no technical sheet, NIT or ANN. | `quote_identity_missing`; continue, never attribute by the TERPEL heading alone. |
| SFC | [Public daily report](https://www.superfinanciera.gov.co/info/superfinancierav8/media/MercadoAccionario/Precios/Diarios/d_cog20paao006.htm), accessible with ordinary server-side HTTP. Contains actual ANN, weighted-average price, price date and action title. | Implemented generic ANN-routed fallback; the reported ANN must independently match RNVE. |
| Grupo Aval | Previous verification returned a public shell without eligible quote rows or identity evidence. | No working quote/identity interface verified; do not fabricate an attempt or use index widgets. |
| Terpel investor page | [Issuer page](https://www.terpel.com/accionistas-e-inversionistas) responded 200 and advertises a closing-price widget; inspected public text did not supply NIT/ANN for the quote. | Not enabled as an identity-qualified provider. A first-party domain alone is not the required match. |
| FMP | [Documented symbol-based JSON quote API](https://site.financialmodelingprep.com/developer/docs/stable/quote). Documentation provides signup/free/premium paths but does not establish Terpel coverage or a Colombian NIT/ANN match. | Not enabled. No authenticated coverage test was run; no account, key or paid service was added. |

The new default source is a public HTTP report, **not an invented JSON API or private endpoint**.
Live Terpel validation returned ANN `COG20PAAO006`, value `18,698.06` COP and price date
`12/11/2026`. This is `price_kind=daily_weighted_average`, not a last-trade price. The API
retains `price_date` without inventing a time and leaves ticker null because this report supplies
none. The UI displays the issuer name in that case and labels the metric explicitly.
The report calls the class PRIVILEGIADA while RNVE labels the same ANN Acciones ordinarias;
that conflict is preserved in `source_note` and shown with the observation.

[SFC methodology](https://www.superfinanciera.gov.co/info/superfinancierav8/media/MercadoAccionario/Precios/Diarios/metodologia.htm)
explains that its price is a weighted daily average, can carry forward when no trade occurs,
and may substitute book value after prolonged inactivity. No present trading or liquidity
conclusion follows from a successful identity match. The source date and retrieval time remain
separate; the cache lifetime measures retrieval age, not market recency.

### Retrieval and failure behavior

- Route only verified 12-character alphanumeric ANN values to the fixed SFC host/path;
  parse and compare the independently reported code, not the filename alone.
- Validate the observed four-column weighted-price table and calendar date; no inferred prices.
- Bound body size and total operation time; retry only transport failures, 429 and 5xx, with
  bounded backoff and Retry-After. Do not retry 4xx or malformed identity/price data.
- Reuse a separate provider-scoped cache, advisory lock, raw source record, private HTML
  artifact hash and ingestion snapshot. Successful and failed attempts have a 15-minute cooldown;
  source-specific refresh bypasses that cooldown for that provider only.
- `exchange_listing.attempts` exposes provider, URL, status, last-attempt time and sanitized
  error code. Unconfigured or skipped providers are clearly distinguished from actual requests.
- If there is no matched quote, expand the source summary and show:
  “No se ha establecido una coincidencia exacta por NIT, ANN o razón social con una cotización.
  Consulte otras fuentes; esto no confirma ausencia de acciones.”
