# Roadmap

Phase 1 implements company identity search and registration-scoped profiles. Phase 2 adds local
RNVE issuer ingestion, registered securities, conservative matching, snapshots, and the Capital
Markets profile. BVC corroboration and ownership remain unknown pending authorized evidence.

Next engineering priorities:

1. Add scheduled, bounded source contract monitoring and metadata caching, with schema drift alerts,
   query latency measurements, and operator-controlled refresh policies.
2. Validate a representative set of multi-registration/NIT conflicts with authoritative evidence;
   design reviewed entity reconciliation and source-ID replacement handling without automatic merges.
3. Prepare deployment access controls, privacy/retention policies, and browser end-to-end accessibility
   tests before expanding public usage or adding new datasets.

Later phases require independent source discovery and licensing/privacy review:

- **Phase 2 follow-up:** establish authorized documented issuer-export automation and BVC listing
  access, add authenticated match review, and validate historical/cancelled source formats.
- **Phase 3 — Financial intelligence:** Supersociedades/SFC statements with periods, currencies,
  restatements, field-level evidence, and deterministic ratios. No inferred financials.
- **Phase 4 — Selectable screening:** opt-in SECOP, SIC integration proceedings, and Contraloría
  datasets with source-specific evidence and ambiguity review. Missing matches are not blanket clearance.
- **Phase 5 — Grounded briefings:** summaries reference verified normalized records and evidence.
  Deterministic code computes financial results; language models cannot invent findings or resolve identity.

Phases 3–5 remain unimplemented. Phase 2 source-access limitations and unassessed attributes are
explicit in the UI and [operating guide](capital-markets.md).
