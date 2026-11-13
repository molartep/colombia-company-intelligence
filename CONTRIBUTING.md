# Contributing

Use Python 3.12+ and Node 24. Start with the README and `docs/sources.md`.

1. Create a feature branch. Keep changes scoped to one outcome.
2. Add meaningful regression tests. Use clearly synthetic company fixtures only.
3. Run `make lint`, `make test`, `make test-db`, and `make build`.
4. Update API/schema/source documentation when behavior changes.
5. Open a pull request explaining the problem, resulting behavior, and executed validation.

Never commit credentials, raw registry records, local databases, or natural-person identifiers.
Do not make standard tests dependent on government services. Run `make smoke` explicitly when
changing the RUES integration. Schema changes need an Alembic revision with reversible operations.

A new source needs verified metadata, documented licensing and privacy considerations, bounded
contract fixtures, and explicit provenance. Searchable registration adapters may implement
`CompanyDataSource`; financial/screening sources should use their own appropriate interfaces.
Do not implement unrequested future-phase features as part of a maintenance change.

Report a security/privacy issue privately to the repository maintainer through GitHub's private
vulnerability reporting if enabled; do not post personal data or credentials in public issues.
