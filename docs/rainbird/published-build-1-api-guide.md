# government_involvement_profile 2 — Studio API connection guide

Decision model version 1. How the Studio API itself works (sessions, replies, questions, evidence): https://docs.rainbird.ai/rainbird/developer-docs/api-reference/decisions

## Connection

- **Base URL:** https://enterprise-api.rainbird.ai
- **kmID:** `738e8674-b78f-4eee-9ad7-c7d13dfa7221`
- **Key:** `X-API-Key` header — a Platform API key from the account this decision model is published in.
- **Engine:** `x-rainbird-engine: rbx` header on every call.
- Every build publishes a new version of the decision model with a new kmID; this guide is for the kmID above.

## How a call goes

1. `GET /start/{kmID}` opens a session and returns its `id`.
2. `POST /{sessionID}/inject` takes an array of facts: `{ "subject", "relationship", "object", "certainty" }`.
3. `POST /{sessionID}/query` takes `{ "subject", "relationship" }` and returns `result` (the answers) or `question` (a value the engine needs).
4. `POST /{sessionID}/response` answers a question with `{ "answers": [ { "subject", "relationship", "object", "certainty" } ] }` and returns the next `result` or `question`.
5. `GET /analysis/evidence/{factID}/{sessionID}` returns the evidence for an answer whose factID holds `:RF:`; https://evidence.raelog.ai shows it as a tree.

## Notes for callers

Subject is evaluation; contracts are contract_1, contract_2… linked by contains_contract. Dates YYYY-MM-DD; booleans true/false. Leave out any fact that is unknown, never guess, and never send outcomes or sufficiency as inputs.

## Queries (29)

| Subject | Relationship | Answer |
| --- | --- | --- |
| Evaluation Context | eligible_contract | Government Contract |
| Evaluation Context | historical_witness | Government Contract |
| Evaluation Context | recent_witness | Government Contract |
| Evaluation Context | execution_witness | Government Contract |
| Evaluation Context | execution_resolved_contract | Government Contract |
| Evaluation Context | attribution_gap_contract | Government Contract |
| Evaluation Context | temporal_gap_contract | Government Contract |
| Evaluation Context | execution_gap_contract | Government Contract |
| Evaluation Context | signature_contradiction | Government Contract |
| Evaluation Context | status_contradiction | Government Contract |
| Evaluation Context | incomplete_coverage_reason | Evidence Diagnostic |
| Evaluation Context | missing_coverage_fact | Evidence Diagnostic |
| Evaluation Context | direct_coverage | true / false |
| Evaluation Context | temporal_coverage | true / false |
| Evaluation Context | execution_coverage | true / false |
| Evaluation Context | direct_participation | Decision Outcome |
| Evaluation Context | historical_participation | Decision Outcome |
| Evaluation Context | recent_participation | Decision Outcome |
| Evaluation Context | currently_reported_execution | Decision Outcome |
| Evaluation Context | direct_participation_sufficiency | Evidence Sufficiency |
| Evaluation Context | historical_participation_sufficiency | Evidence Sufficiency |
| Evaluation Context | recent_participation_sufficiency | Evidence Sufficiency |
| Evaluation Context | currently_reported_execution_sufficiency | Evidence Sufficiency |
| Evaluation Context | common_diagnostic | Evidence Diagnostic |
| Evaluation Context | direct_participation_diagnostics | Evidence Diagnostic |
| Evaluation Context | historical_participation_diagnostics | Evidence Diagnostic |
| Evaluation Context | recent_participation_diagnostics | Evidence Diagnostic |
| Evaluation Context | currently_reported_execution_diagnostics | Evidence Diagnostic |
| Government Contract | execution_past_scheduled_end | true / false |

## Facts to inject (18)

By subject, most used first. A fact you do not inject is asked for as a question, where the decision model has one; otherwise it stays unknown.

| Subject | Relationship | Value | When not injected |
| --- | --- | --- | --- |
| Evaluation Context | source_stale | true / false | not asked — inject it |
| Evaluation Context | contains_contract | Government Contract; several — one fact per value | not asked — inject it |
| Evaluation Context | identity_verified | true / false | not asked — inject it |
| Evaluation Context | query_complete | true / false | not asked — inject it |
| Evaluation Context | as_of_date | date (YYYY-MM-DD) | not asked — inject it |
| Evaluation Context | lookback_start_date | date (YYYY-MM-DD) | not asked — inject it |
| Evaluation Context | contract_count | number | not asked — inject it |
| Evaluation Context | lookback_months | number | not asked — inject it |
| Government Contract | signature_conflict | true / false | not asked — inject it |
| Government Contract | execution_status_conflict | true / false | not asked — inject it |
| Government Contract | attribution_verified | true / false | not asked — inject it |
| Government Contract | signature_band | Signature Band; known: historical \| recent \| missing \| future | not asked — inject it |
| Government Contract | signature_date | date (YYYY-MM-DD) | not asked — inject it |
| Government Contract | execution_status | Execution Status; known: execution \| non_execution \| unknown | not asked — inject it |
| Government Contract | observation_available | true / false | not asked — inject it |
| Government Contract | reported_status | Reported Status Text | not asked — inject it |
| Government Contract | scheduled_end_date | date (YYYY-MM-DD) | not asked — inject it |
| Government Contract | value_conflict | true / false | not asked — inject it |

Worked out by the decision model's rules (inject only to override them): eligible_contract, historical_witness, recent_witness, execution_witness, execution_resolved_contract, attribution_gap_contract, temporal_gap_contract, execution_gap_contract, signature_contradiction, status_contradiction, incomplete_coverage_reason, missing_coverage_fact, direct_coverage, temporal_coverage, execution_coverage, direct_participation, historical_participation, recent_participation, currently_reported_execution, direct_participation_sufficiency, historical_participation_sufficiency, recent_participation_sufficiency, currently_reported_execution_sufficiency, common_diagnostic, direct_participation_diagnostics, historical_participation_diagnostics, recent_participation_diagnostics, currently_reported_execution_diagnostics, execution_past_scheduled_end.

## Example — eligible_contract

A subject named after its concept, and a value in `<…>`, are placeholders to replace. The same calls in three languages.

### curl

```sh
# 1 · Start a session
curl https://enterprise-api.rainbird.ai/start/738e8674-b78f-4eee-9ad7-c7d13dfa7221 \
  -H "X-API-Key: $PLATFORM_API_KEY" \
  -H "x-rainbird-engine: rbx"
# → { "id": "<session id>" }   then: export SESSION_ID=<session id>

# 2 · Inject facts
curl -X POST https://enterprise-api.rainbird.ai/$SESSION_ID/inject \
  -H "X-API-Key: $PLATFORM_API_KEY" \
  -H "x-rainbird-engine: rbx" \
  -H "content-type: application/json" \
  -d '[
  { "subject": "evaluation", "relationship": "source_stale", "object": true, "certainty": 100 },
  { "subject": "evaluation", "relationship": "contains_contract", "object": "<contains_contract>", "certainty": 100 },
  { "subject": "evaluation", "relationship": "identity_verified", "object": true, "certainty": 100 },
  { "subject": "evaluation", "relationship": "query_complete", "object": true, "certainty": 100 }
]'

# 3 · Query
curl -X POST https://enterprise-api.rainbird.ai/$SESSION_ID/query \
  -H "X-API-Key: $PLATFORM_API_KEY" \
  -H "x-rainbird-engine: rbx" \
  -H "content-type: application/json" \
  -d '{ "subject": "evaluation", "relationship": "eligible_contract" }'
# → { "result": [ … ] } — or { "question": { … } }: answer it with /response
```

### JavaScript

```javascript
const BASE = 'https://enterprise-api.rainbird.ai';
const headers = { 'X-API-Key': process.env.PLATFORM_API_KEY, 'x-rainbird-engine': 'rbx', 'Content-Type': 'application/json' };
const call = (path, body) =>
  fetch(`${BASE}/${path}`, { method: body ? 'POST' : 'GET', headers, body: body && JSON.stringify(body) }).then((r) => r.json());

// 1 · Start a session
const { id: sessionId } = await call('start/738e8674-b78f-4eee-9ad7-c7d13dfa7221');

// 2 · Inject facts
await call(`${sessionId}/inject`, [
  { subject: 'evaluation', relationship: 'source_stale', object: true, certainty: 100 },
  { subject: 'evaluation', relationship: 'contains_contract', object: '<contains_contract>', certainty: 100 },
  { subject: 'evaluation', relationship: 'identity_verified', object: true, certainty: 100 },
  { subject: 'evaluation', relationship: 'query_complete', object: true, certainty: 100 }
]);

// 3 · Query
let reply = await call(`${sessionId}/query`, { subject: 'evaluation', relationship: 'eligible_contract' });
// reply.result holds the answers; reply.question, a question to answer with /response
```

### Python

```python
import os, requests

BASE = 'https://enterprise-api.rainbird.ai'
headers = {'X-API-Key': os.environ['PLATFORM_API_KEY'], 'x-rainbird-engine': 'rbx'}

# 1 · Start a session
session_id = requests.get(f'{BASE}/start/738e8674-b78f-4eee-9ad7-c7d13dfa7221', headers=headers).json()['id']

# 2 · Inject facts
requests.post(f'{BASE}/{session_id}/inject', headers=headers, json=[
  {'subject': 'evaluation', 'relationship': 'source_stale', 'object': True, 'certainty': 100},
  {'subject': 'evaluation', 'relationship': 'contains_contract', 'object': '<contains_contract>', 'certainty': 100},
  {'subject': 'evaluation', 'relationship': 'identity_verified', 'object': True, 'certainty': 100},
  {'subject': 'evaluation', 'relationship': 'query_complete', 'object': True, 'certainty': 100},
]).raise_for_status()

# 3 · Query
reply = requests.post(f'{BASE}/{session_id}/query', headers=headers, json={'subject': 'evaluation', 'relationship': 'eligible_contract'}).json()
# reply['result'] holds the answers; reply['question'], a question to answer with /response
```
