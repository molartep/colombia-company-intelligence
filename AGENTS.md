# Interface development

Before frontend changes, read [the brand and UI manual](docs/design/BRAND_AND_UI_GUIDELINES.md).

- Reuse `frontend/src/design-tokens.css` and existing components; preserve the current visual identity.
- Maintain keyboard access, visible focus, accessible labels, contrast and reduced-motion behavior.
- Support English and Spanish; use centralized translations and shared locale formatters.
- Preserve original source values in storage, API payloads and filter parameters. Display-only casing is allowed solely for fields in the manual’s growing external-field registry; never translate source values.
- Follow existing responsive grids and local table scrolling; inspect desktop/mobile and long text.
- Avoid unnecessary dependencies, duplicated components and new visual conventions.
- Test relevant populated/loading/empty/error/stale states; run lint, type checks, tests and builds.
- Do not change APIs, schemas, identity matching or financial calculations for visual reasons.
- Update the manual and visual references whenever deliberately changing the design system.
