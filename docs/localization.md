# English and Spanish localization

The frontend uses `react-i18next` and a single shared i18next instance. The main navigation's
EN/ES button group switches the entire interface immediately, including open company profiles,
source evidence, filters, dialogs, errors, charts and contract details. Navigation and current
query/filter state are preserved. Language changes do not refetch company/source data.

## Preferences and fallback

`cci.language` in localStorage stores `en` or `es`. Without a valid saved preference, the first
supported language in `navigator.languages` is used (regional variants such as `en-GB` and
`es-CO` are accepted). Spanish is the fallback for unsupported browser languages and missing
English translations. Blocked storage does not prevent switching. The document's `lang` and
meta description follow the active language. Keyboard focus, accessible language names and
`aria-pressed` expose the selected toggle state.

## Application text versus source evidence

Catalogs live in `frontend/src/i18n/locales/en.json` and `es.json`, organized by feature:
`search`, `overview`, `capitalMarkets`, `governmentContracts`, `parameters`, `advanced`,
`navigation`, `fields`, `feedback`, `errors` and shared `common` entries.

Translate interface labels, normalized application classifications, explanatory prose and
application-generated notifications. Render external evidence **directly**: legal/company names,
RUES status/organization/CIIU labels, SFC security names and report fields, ratings, SECOP
contract descriptions, raw statuses, buyer names and procurement modalities. Do not trim,
translate, or pass these values to `t()`, even if they happen to equal a translation
key or common UI word. Technical codes, identifiers, URLs and source payloads remain unchanged.
The explicitly approved SECOP status/entity/modality fields display in uppercase, including filters; stored evidence, responses and outgoing filter values keep their originals. All other fields preserve original casing. See the growing registry in the brand manual.

`i18n/messages.ts` translates a finite allowlist of existing **application-generated** backend
messages, warnings and source-descriptor prose using `messageKeys.json`. This compatibility
layer leaves unknown messages unchanged, keeping unknown evidence safe. Use it only at known
application-prose boundaries; never for arbitrary source fields. New backend prose should gain
an explicit allowlist entry or a stable message code with a frontend translation. Request errors
use machine codes with localized safe fallback text; raw server error messages are not displayed.
Backend responses, stored evidence, API identifiers, query parameters and database schemas are
language-independent. No backend migration is required.

## Adding a module

1. Add matching semantic keys to both catalogs under a feature namespace. Prefer short keys such
   as `futureModule.emptyState`. Keep complete sentences together; interpolate counts/variables
   rather than joining translated sentence fragments. Use `_one`/`_other` for plural forms.
2. In a component, use `const { t } = useTranslation()`; existing modules use the equivalent
   shared `useLanguage()` subscription plus exported `t`. Call `t()` while rendering or computing
   a value, not once in a module-level constant. Static lookup maps should store keys or be factories.
3. Translate accessible names, titles, placeholders, chart text and every asynchronous state too.
   External option labels and filter values remain original; only surrounding controls translate.
4. Use the shared formatting helpers and add EN/ES tests. Never include language in API queries
   or evidence identities. Reuse components across languages.

## Numbers, dates and money

`i18n/format.ts` uses Intl with `en-US` or `es-CO`. Decimal strings go directly to
`Intl.NumberFormat`, avoiding binary floating-point coercion and retaining their fractional
precision, including values above JavaScript's safe-integer range. Currency formatting retains
the reported currency code and never converts currencies. Quotes without currency information
show the amount without an assumed currency. SECOP's existing explicit COP policy is unchanged.
Counts are formatted separately; identifiers and raw original-report values are not reformatted.

Date-only events use UTC to prevent a local timezone from moving the calendar date. Timestamps
use the application's Colombia timezone, `America/Bogota`; invalid source dates remain visible
as evidence or retain the existing Review treatment. Raw values in source-report disclosures
remain unchanged. Modern supported browsers must implement Intl decimal-string formatting.

## Verification

```sh
cd frontend
npm ci
npm run lint
npm run format:check
npm run typecheck
npm test
npm run build
```

`i18n.test.tsx` covers language switching on every existing route, saved preferences and browser
fallback, blocked storage, Spanish missing-key fallback, catalog/interpolation parity, screening
states, decimal precision and unchanged RUES/SFC/SECOP values. `i18n-coverage.test.ts` rejects
untranslated literal JSX text/accessibility attributes and missing literal translation keys.
An explicit small allowlist permits invariant proper names, source quotations and technical
abbreviations. Dynamic source evidence must still be reviewed at its rendering boundary.
Existing feature tests run in English; focused localization tests switch to Spanish and back.

Browser validation was also performed against localhost with mocked deterministic source
responses: all six existing routes, preference persistence after reload, browser-language and
unsupported-language fallback, original SECOP values, and desktop/mobile Government Contracts
layouts, with no browser runtime errors. This validates localization without depending on live
third-party availability.

## Technical terminology

Use the English terms **snapshot, cache, fallback, parser and runtime** in Spanish technical
copy. See the [Platform References glossary](platform-references.md#spanish-technical-glossary)
for their meanings and the distinction between fallback, backups and supporting evidence.
