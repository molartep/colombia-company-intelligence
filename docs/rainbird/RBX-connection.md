# Published RBX connection

The [user-supplied connection guide](published-build-1-api-guide.md) identifies this deployment:

- Enterprise API: `https://enterprise-api.rainbird.ai`
- Model/build ID: `738e8674-b78f-4eee-9ad7-c7d13dfa7221`
- Engine header on every request: `x-rainbird-engine: rbx`
- Credentials: account Platform API key in `X-API-Key`

## Add the key locally

Open `backend/.env` and fill in the existing blank line:

```dotenv
RAE_API_KEY=your_platform_api_key
```

This local file was prepared with the build ID and Enterprise/RBX settings. It is Git-ignored and
has owner-only permissions (0600). Existing root development settings were preserved when creating it.
Never put the key in `.env.example`, a frontend `VITE_` variable, source code or a chat message.
If evidence access requires an additional key, fill `RAE_EVIDENCE_KEY` in the same private file.

Local configuration:

```dotenv
RAE_ENABLED=false
RAE_EXECUTION_MODE=disabled
RAE_API_BASE_URL=https://enterprise-api.rainbird.ai
RAE_ENGINE=rbx
RAE_MODEL_REFERENCE_MODE=published_build
RAE_MODEL_ID=738e8674-b78f-4eee-9ad7-c7d13dfa7221
RAE_API_KEY=
RAE_EVIDENCE_KEY=
RAE_REQUEST_TIMEOUT_SECONDS=60
```

Leave `RAE_MODEL_VERSION` unset in published-build mode. According to this deployment's guide, each
build gets a new kmID; update `RAE_MODEL_ID` from its new guide whenever republishing. This is distinct
from legacy `version` mode, which explicitly sends the configured integer version. If start returns
`kmVersion.id`, it is retained; otherwise metadata explicitly says `published-build:<kmID>` rather than
inventing a vendor-returned version identifier.

## Run the live synthetic connection check

From the repository root:

```sh
cd backend
.venv/bin/python ../scripts/rae_smoke.py --live
```

The command reads `backend/.env` because it runs from `backend/`. No server restart is necessary for
this one-shot command. Environment variables exported by your shell override `.env` values.
`--live` enables only this fixed repository synthetic fixture, for this process; it does not enable
company processing. Existing environment-enabled experiments remain supported without `--live`.

The smoke test compares four decisions and four sufficiency values with explicit expectations,
requires complete native evidence, and reports round-trip duration and diagnostic counts. A blank
key returns the safe code `not_configured` without making an external call. It never prints keys,
raw payloads, company names or NITs. No live test has been performed until a valid key is supplied.

After migrations, `--live --persist` stores a successful synthetic evaluation in the private local DB;
`--refresh` bypasses its cache. Cache keys include build/reference mode, engine, API base and all inputs.

## Compatibility changes

- JSON Boolean values are transmitted as booleans, not strings.
- `signature_conflict`, `execution_status_conflict` and `value_conflict` are explicit optional inputs;
  omissions remain unknown. The synthetic fixture explicitly supplies false values. The production
  mapper never invents false diagnostics from missing upstream information.
- Available contract end dates are supplied as `scheduled_end_date`.
- Common and per-dimension diagnostic result facts are retained separately from CCI warnings.
- Response `sid` is checked when supplied; absent `sid` is accepted for the guide's RBX response shape.
- Unexpected questions stop the headless run; no `/response` answers are fabricated.
- Evidence is fetched only for inferred `:RF:` root answers. Full trees are requested; 400/413 uses
  individual-fact traversal with depth/node/time bounds, cycle protection and explicit missing branches.
- Terminal decision/sufficiency inputs are rejected before any external call. The guide's suggestion
  that callers can override inferred facts is deliberately not used by CCI.

The model's actual response shapes, evidence-key requirements and business-rule agreement still need
validation using the live synthetic command. Real-company transmission remains blocked in every mode.
