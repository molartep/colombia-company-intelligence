# Optional USD presentation

Original values and currency metadata stay unchanged in persistence, API source projections,
filters, stored summaries and sorting. The company header has an always-visible Currency card at
the top right, with COP/USD choices. USD replaces COP amounts in their existing display elements in Government Contracts (summary/activity/table/detail) and Capital Markets
(quoted prices/authorized amounts). Converted values have an `≈` prefix, retaining the original
font size/weight and placement. Titles and currency column labels change with the displayed unit.
Selecting COP restores exact source displays. Other explicit currencies and unknown currencies are untouched.

## Provider assessment — 2026-11-24

Selected: [SFC TRM dataset 32sa-8pi3](https://www.datos.gov.co/d/32sa-8pi3), published by the
Superintendencia Financiera de Colombia, accessed through the fixed datos.gov.co SODA endpoint.
The [SFC methodology page](https://www.superfinanciera.gov.co/publicaciones/60819/informes-y-cifrascifrasestablecimientos-de-credito/informacion-periodicadiariatasa-de-cambio-representativa-del-mercado-trm-60819/)
identifies SFC as the certifying authority. This is a daily reference, not a trading quote.
The dataset metadata declares daily updates and license `CC_40_BY_SA` (Creative Commons
Attribution Share-Alike 4.0). Attribution and the source URL accompany rate metadata; redistributed
rate data remains subject to that license, separately from the software MIT license. The minimized
[assessment snapshot](discovery/trm-provider.json) records the reviewed fields and attribution.

[Socrata's official token policy](https://dev.socrata.com/docs/app-tokens.html) permits simple
unauthenticated queries with shared-IP throttling; optional `SOCRATA_APP_TOKEN` increases capacity.
No guaranteed numeric free allowance or uptime SLA was established. Limits can change and HTTP
429 must be handled. The existing backend transport enforces timeouts, fixed hosts, no redirects
and a 2 MB response cap. This connector performs one one-row query per process per hour, serialized
under a lock; failures have a 60-second cooldown and no immediate retries. A multi-process fleet
would need a shared rate cache to keep aggregate demand bounded. No paid fallback or browser token
is introduced. Endpoint availability and schema validation do not establish permanent reliability.

## Rate selection and precision

`GET /api/v1/presentation/usd-rate` returns `cop_per_usd` as a decimal string, source name/link,
`effective_date`, `effective_until` (inclusive Colombia calendar dates), retrieval timestamp,
`manual=false`, `stale`, `provider_failed`, the rate-data license URL and rounding policy. The query selects the latest published
row whose start date is no later than today in America/Bogota. It does not use tomorrow's rate just
because it was published early. This is the **latest published effective** rate known at retrieval;
an hourly cache is not an instantaneous publication feed.

The provider must return a positive plain decimal, `unidad=COP`, and ordered validity dates.
Weekends and holidays use the published validity interval, without inventing calendar exceptions.
An expired interval or provider failure disables reference conversion, keeps COP visible and
allows retry or manual entry. Labels stay COP until a usable rate is available. A failed refresh may return prior metadata flagged stale; it is
never used for conversion. Without prior metadata the endpoint returns a structured 503 error.

Manual mode requires a positive decimal **COP per USD** rate, up to 12 integer and 12 fractional
digits, using a dot. Selecting USD initially populates the editable field from the current effective
TRM. Editing creates an explicit manual override; an icon-only refresh arrow restores the published
reference. There is no manual date input: the Colombia date of entry is recorded as manual audit
context in the existing export rate metadata, not a claim about historical market validity.
Manual status stays visible; source, effective interval, calculation and limitations are available
through the information-icon tooltips. The selection is local to the profile session and defaults
to COP. Automatic provider polling never overwrites an edited manual rate.

`USD = COP / rate`. Browser BigInt division and backend Decimal division use half-even rounding to
USD cents; no JavaScript Number conversion is used. USD is an estimate at the selected rate for
presentation, not historical conversion at signature/quote dates, a settlement value or revenue.
Original values and summary aggregates retain their original precision. CSV/JSON exports store
USD in a separate `presentation_usd` field and attach the rate metadata; they never overwrite value
or currency. Export revalidates reference rates server-side, so a later export can use a newly
published effective rate; the file records the actual rate used.
