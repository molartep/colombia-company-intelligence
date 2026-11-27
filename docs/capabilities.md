# Current capability matrix

Repository review: 2026-11-24. **Implemented** means a working code path with contract tests,
not universal source availability. **Partial** means usable with material coverage/access limits.
**Experimental** means a connector exists but broad live coverage is unverified. **Planned** means
no working end-to-end capability. Historical phase numbers describe delivery order, not readiness.

| Capability | Status | Verified implementation and limits |
| --- | --- | --- |
| Company search and registration profiles | Implemented | RUES `c82u-588k`, NIT/name search, pre-pagination filters, registration-scoped UUIDs, source versions, stale fallback. No company municipality/department in verified schema. [Source fields](sources.md), [filters](advanced-filters.md). |
| RNVE issuer directory and securities | Partial | Official XLSX import, conservative identity links, issuer details and securities retrieval for verified issuers. Coverage depends on imported directory and retrievable reports; incomplete imports cannot establish absence. Ownership remains unknown. [Operating guide](capital-markets.md). |
| Quotes and current trading coverage | Experimental | BVC configured locators, La República discovery, SFC daily-price fallback. Exact identity required; live verification is case-specific. BVC 403 and empty publisher tables can block retrieval. Daily weighted averages are not last trades; none is a real-time feed. [Access evidence](quote-source-access.md). |
| Government Contracts | Implemented | SECOP II `jbjy-vk9h`, confirmed supplier NIT, explicit non-group suppliers, bounded snapshot, filtering, sorting, detail, deterministic summaries, stale-success retention. Not comprehensive screening. [Methodology](secop-screening.md). |
| Currency presentation | Implemented | Opt-in COP→USD using latest published effective SFC TRM or a labeled manual rate. Original amounts retained; no historical FX reconstruction. [Provider and arithmetic](currency-presentation.md). |
| Research and filtered contract export | Implemented | Public CSV/JSON projections, 1,000 rows / 5 MiB, provenance and completeness warnings, optional separate USD presentation. Local evidence only. [Schema and limits](exports.md). |
| Platform References | Implemented | `/references`, `/advanced` redirect, architecture/workflows, local readiness and counts, capability matrix. Counts are local history, not live source coverage. [Page guide](platform-references.md). |
| Financial statements and ratios | Planned | No statements, financial ratios, revenue inference or historical FX calculation. Requires source discovery, rights, periods/currencies/restatements and deterministic calculation tests. |
| Corporate events | Planned | Profile placeholder only. Requires event taxonomy, licensed sources, identity and dated evidence. |
| Additional screening and grounded briefings | Planned | No SECOP I, SIC, Contraloría, sanctions/risk clearance or LLM research briefings. Requires independent adapters, rights/matching validation and completeness semantics before source selection or summaries. |

## Coverage and monetary conventions

RUES, RNVE and SECOP are independent evidence paths. A name candidate is not a verified identity;
RNVE registration is not proof of current trading; contracts are not revenue, payment or adverse
findings. SECOP currency is absent upstream: `COP` / `application_policy` is the explicit application
convention. Financial strings retain precision; currencies are never silently pooled or relabeled.
USD estimates use **COP per USD**, `USD = COP / rate`, half-even rounding to cents, and keep rate
source, effective interval and manual status. They do not recreate historical purchasing power.

SECOP preflight rejects portfolios above `SECOP_MAX_ROWS` (default **5,000 source rows**, configurable
up to 10,000), before deduplication. There are no partial new snapshots or totals. A prior successful
snapshot can remain visible as stale. The independent export cap is 1,000 output rows; it cannot
bypass screening limits. No successful snapshot means no contract export, not a clean empty file.

## Historical context

The first roadmap called all selectable screening “Phase 4” and financial intelligence “Phase 3”.
SECOP II shipped ahead of that sequence and its implementation notes called it “Phase 3”. Those
labels remain useful when reading migrations and dated validation logs; they do not mean SECOP is
future work or that financial statements shipped. “Advanced” was the former References page name;
advanced **search filters** remain a separate current feature. Earlier claims of BVC being entirely
unimplemented describe the pre-connector state, not today's limited quote integrations.

## Government Involvement live mode

Authorized company reasoning is implemented for verified, immutable SECOP II snapshots. The backend
reuses supplier matching, sends only minimized pseudonymous facts to Rae, persists native decisions,
evidence, failures and local source references, and caches by source/model/policy/date. GET evaluates
on cache miss; same-origin POST reasoning refresh has company rate/cooldown controls. Prior native
findings remain qualified if reevaluation fails. No Python classification fallback is used.
The card shares a responsive 2×2 grid with the three activity visualizations. Live synthetic reasoning and one authorized company evaluation passed; ongoing minimized company transmission has been explicitly approved. See [Rae manual](RaeManual.md).
