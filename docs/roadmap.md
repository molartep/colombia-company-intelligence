# Roadmap

Use the [current capability matrix](capabilities.md) for readiness and source coverage. Company
identity, SECOP II Government Contracts, References, optional currency presentation and bounded
exports are implemented. Capital Markets is usable with incomplete directory/report coverage;
quote connectors remain experimental in coverage. Financial statements, corporate events and
additional screening sources are planned.

## Backlog and prerequisites

| Future work | Prerequisites and acceptance boundary |
| --- | --- |
| Source monitoring and drift alerts | Bounded metadata probes, documented publishing cadence, operator refresh policy and safe logs. Local References counts alone do not provide upstream monitoring. |
| Reviewed identity reconciliation | Representative multi-registration/NIT conflicts, authoritative evidence, authenticated review and audit/undo policy. Preserve registration UUIDs; no automatic merges. |
| Larger SECOP portfolios | Stable complete retrieval/aggregation and snapshot consistency strategy, load/rate tests, source-access assessment. Preserve no-partial-totals behavior until validated. [Current cap](secop-screening.md). |
| Wider quote coverage | Reproducible authorized access, provider terms, exact identity evidence, provider-specific timestamps, historical/cancelled-format validation. [Existing access assessment](quote-source-access.md). |
| Financial statements and ratios | Licensed Supersociedades/SFC discovery, identity links, reporting periods, original currencies, restatements and field-level evidence; deterministic tested calculations. |
| Corporate events | Source discovery/rights, event taxonomy, identity evidence and source-effective/retrieval dates. |
| SECOP I, SIC, Contraloría and other screening | Independent source/rights/privacy validation, adapters, ambiguity handling, completeness states and tests before a selectable-source UI. No blanket clearance. |
| Grounded briefings | Verified evidence from the relevant implemented sources, citation coverage, uncertainty and deterministic calculations. A language model cannot invent missing records or resolve identity. |
| Expanded public operation | Deployment-specific access controls, data rights, privacy/retention policies, source capacity assessment and browser/assistive-technology tests. Existing production guards do not establish public-launch readiness. |

## Delivery history

Phase 1 delivered registration identity; Phase 2 introduced the capital-market evidence layer.
The original aspirational Phase 3 (financial intelligence), Phase 4 (selectable screening) and
Phase 5 (briefings) were not release commitments. SECOP II was subsequently implemented under the
historical “Phase 3” label in its migration/validation notes. Financial intelligence and screening
beyond SECOP II remain planned. Read dated validation records as historical evidence, not current
coverage guarantees.
