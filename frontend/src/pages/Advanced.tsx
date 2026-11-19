import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { DirectoryImport } from '../components/DirectoryImport'
import { Failure, Loading } from '../components/Feedback'
import { dateTime } from '../utils'

const workflows = [
  {
    title: '1. Search and registration identity',
    body: 'Submitting Search sends GET /api/v1/companies with a NIT or name, fixed-code filters and bounded pagination. The FastAPI adapter normalizes inputs, escapes controlled Socrata queries and applies filters and ranking before LIMIT/OFFSET. Live name ranking runs across all matching source rows; the API requests one extra row to determine whether another page exists rather than calculating an expensive total.',
    detail:
      'Each official registration row has its own persisted UUID, keyed by source plus source row identity. NIT is indexed but is not unique. Shared NITs, branches and separate registrations are not merged. Exact NIT/DV evidence, exact names, normalized names and partial matches stay distinguishable; the platform does not invent confidence percentages.',
  },
  {
    title: '2. Persistence, provenance and outage fallback',
    body: 'Search results are upserted into Postgres using SQLAlchemy. Companies and aliases support later lookup; private source records preserve payload versions and hashes. Source timestamps, retrieval times and report observation times remain separate. Public APIs return allowlisted evidence, never the complete raw payload or database credentials.',
    detail:
      'HTTPX applies bounded retries and concurrency. If an official source fails, usable cached evidence can be returned with an explicit stale warning. Without usable evidence, the request fails instead of reporting zero matches. Profile reads use the cached registration; an explicit refresh retrieves only that same RUES source row. Browser search results stay in memory for 30 minutes, and returning from a profile does not automatically repeat the search.',
  },
  {
    title: '3. Directory import and conservative reconciliation',
    body: 'The import action opens a fresh server-side browser, visits the official RNVE directory and selects DESCARGAR EMISORES → REPORTE EXCEL. It does not use a private API or copied browser credentials. If the public controls fail, an operator can upload the same issuer-only XLSX. Only this one dataset requires initial import; there is no mandatory bulk securities or quote seed.',
    detail:
      'The existing parser rejects oversized archives, formulas, macros, external workbook links, schema changes, duplicate regulatory keys and future report dates. Issuers are upserted by source and regulatory type/code. Exactly ten-digit corporate identifiers are split into NIT/DV only when the checksum validates; trust, fund and foreign-entity identifiers are not truncated into corporate identities. A transaction records a snapshot and reconciles links. UI imports default to incomplete coverage: absence is not a verified negative. Full-directory completeness requires a separately reviewed count and explicit CLI attestation.',
  },
  {
    title: '4. Registrado BVC discovery before pagination',
    body: 'The BVC checkbox searches the imported issuer directory for candidate identities, retrieves issuer-specific RNVE securities evidence and obtains eligible NITs before asking RUES for the result page. It is not restricted to companies previously opened or to rows visible on the current page. Discovery is bounded to ten matching issuers; broad searches must be narrowed.',
    detail:
      'A verified indicator requires a verified issuer relationship and ordinary-share records whose reported market is BVC. NIT collisions, incompatible verification digits and name-only candidates remain unresolved or potential. RNVE registration, BVC registration events, current listing, trading activity and ownership are separate findings. A blank check is not evidence of no registration.',
  },
  {
    title: '5. Capital Markets retrieval and quote fallback',
    body: 'Opening Capital Markets for a verified issuer retrieves missing or stale RNVE summaries and securities reports. Chromium renders public summary pages; HTTPX retrieves the public issuer-specific report. Successful summary and securities caches last 24 hours independently, and failures have independent 15-minute cooldowns. Opening a page without a verified issuer cannot retrieve issuer-specific evidence.',
    detail:
      'Quote resolution tries BVC, then La República, then official SFC daily-price reports, requiring exact identity evidence at each step. La República discovers links from its public stock directory (24-hour cache, at most 100 links), checks up to three candidate technical sheets, and rejects ambiguous matches. Labels only route requests; NIT, ANN or exact legal name establishes identity. Verified mappings retain URL, discovery time and directory hash. Quotes are cached separately (15 minutes by default). More than one common-equity record blocks quote attribution rather than selecting an arbitrary instrument. SFC daily weighted averages are labeled as such, not presented as a current last trade. Manual source refresh targets only the selected connector; the directory uses its import action.',
  },
  {
    title: '6. Runtime boundaries and administration',
    body: 'The local Vite server serves React and proxies relative /api requests to FastAPI. In the production Compose stack, Caddy serves compiled assets and HTTPS, forwarding /api to a single Uvicorn worker. Postgres has no public port. Evidence artifacts and database files use private persistent storage. Migrations run explicitly before startup; an empty database schema contains no invented demo companies.',
    detail:
      'Imports are POST operations with a 10 MiB streamed upload cap and serialized execution. Loopback development allows same-origin operators; deployed servers require a server-configured administrator key. Import downloads have a one-minute cooldown. Production request limits and company-wide manual-refresh intervals are memory-bounded and assume one API process. Backups quiesce writers and preserve both database and evidence; restore checks use an isolated disposable database. Deployment configuration being present does not mean the site is hosted or monitored automatically.',
  },
]

const dependencies: Record<string, string> = {
  sfc_rnve: 'Initial directory import; used by BVC search and all issuer identity matching.',
  sfc_rnve_issuer_details: 'On demand after a verified issuer link; no separate import required.',
  sfc_rnve_securities: 'On demand for discovered/verified issuers; no bulk import required.',
  bvc_listings:
    'Verified ordinary-share identity and configured public-page locator; publisher access can fail.',
  la_republica_stock_directory:
    'Fetched automatically on demand; persisted for 24 hours, up to 100 links; failures retry after 15 minutes.',
  la_republica_quotes:
    'Automatic publisher-directory discovery, then exact identity verification; no company URL setup.',
  sfc_daily_quotes: 'Official daily-price fallback using an exact ANN; not a live trade feed.',
}

export function Advanced() {
  const status = useQuery({ queryKey: ['platform'], queryFn: ({ signal }) => api.platform(signal) })
  const data = status.data
  return (
    <section className="advanced-page">
      <p className="eyebrow">PLATFORM REFERENCE</p>
      <h1>Advanced</h1>
      <p className="parameters-intro">
        Architecture, data readiness and the technical workflow behind each finding.
      </p>
      <section className="panel" aria-labelledby="runtime-status-title">
        <div className="section-heading">
          <h2 id="runtime-status-title">Current data state</h2>
          <button
            className="refresh-button"
            disabled={status.isFetching}
            onClick={() => void status.refetch()}
          >
            {status.isFetching ? 'Checking…' : 'Refresh status'}
          </button>
        </div>
        <p className="muted small">
          Database observations from this server, not live upstream probes. “Not yet checked” means
          no recorded retrieval; it does not establish an outage. Source rows show global connector
          history; company profiles scope evidence to the selected issuer.
        </p>
        {status.isPending && <Loading />}
        {status.isError && <Failure error={status.error} retry={() => void status.refetch()} />}
        {data && (
          <>
            <p className="small">Status checked: {dateTime(data.checked_at)}</p>
            <dl className="platform-counts">
              {Object.entries(data.counts).map(([key, value]) => (
                <div key={key}>
                  <dt>{key.replaceAll('_', ' ')}</dt>
                  <dd>{value.toLocaleString()}</dd>
                </div>
              ))}
            </dl>
            {data.directory_missing && (
              <div className="notice warning" role="alert">
                <strong>RNVE directory is empty.</strong>
                <p>
                  Capital Markets identity matching and Registrado BVC search need this initial
                  import.
                </p>
                <DirectoryImport />
              </div>
            )}
            {data.import_access === 'disabled' && (
              <p className="notice">
                Imports are disabled on this deployment until its administrator configures an import
                key. Search remains available without the BVC filter.
              </p>
            )}
            {data.import_access === 'admin_key' && (
              <p className="notice">
                Directory imports require the administrator key in the import form.
              </p>
            )}
            <div className="table-wrap">
              <table className="platform-sources">
                <thead>
                  <tr>
                    <th>Source</th>
                    <th>Current state</th>
                    <th>Last attempt / success</th>
                    <th>Dependency and workflow</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>
                      <a
                        className="text-link"
                        href={data.rues.dataset_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {data.rues.name} ↗
                      </a>
                    </td>
                    <td>{data.rues.availability.replaceAll('_', ' ')}</td>
                    <td>
                      {dateTime(data.rues.last_checked_at)}
                      <br />
                      Dataset updated: {dateTime(data.rues.last_updated_at)}
                    </td>
                    <td>
                      Live search and registration refresh. Cache grows with use; no initial data
                      import.
                    </td>
                  </tr>
                  <tr>
                    <td>RUES parameter catalog</td>
                    <td>Bundled · {data.parameter_options} options</td>
                    <td>Verified: {dateTime(data.parameter_verified_at)}</td>
                    <td>
                      Versioned code/label snapshot shipped with the app; independent of database
                      row counts.
                    </td>
                  </tr>
                  {data.sources.map((source) => (
                    <tr key={source.id}>
                      <td>
                        <a
                          className="text-link"
                          href={source.source_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {source.name} ↗
                        </a>
                      </td>
                      <td>
                        {source.id === 'sfc_rnve' && data.directory_missing
                          ? 'Import required'
                          : source.last_ingestion_status === 'failed'
                            ? 'Last attempt failed'
                            : !source.last_success_at
                              ? 'Not yet checked'
                              : source.stale
                                ? 'Stale evidence'
                                : 'Cached evidence available'}
                        {source.latest_snapshot && (
                          <p className="small">
                            Observation: {dateTime(source.latest_snapshot.observed_at)}
                            <br />
                            Coverage:{' '}
                            {source.latest_snapshot.complete_current
                              ? 'Complete-current attestation'
                              : 'Not attested complete'}
                          </p>
                        )}
                        {source.last_error && (
                          <p className="small">
                            Recorded error: <code>{source.last_error}</code>
                          </p>
                        )}
                      </td>
                      <td>
                        {dateTime(source.last_attempt_at)}
                        <br />
                        Success: {dateTime(source.last_success_at)}
                      </td>
                      <td>
                        {dependencies[source.id] ??
                          'Consult the source-specific evidence for scope.'}
                        {source.id === 'sfc_rnve' && !data.directory_missing && (
                          <details>
                            <summary>Update issuer directory</summary>
                            <DirectoryImport />
                          </details>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
      <section className="panel">
        <h2>Architecture</h2>
        <ol className="architecture-chain" aria-label="Architecture data flow">
          <li>
            <strong>React + TypeScript</strong>
            <span>Router · TanStack Query · accessible search and evidence views</span>
          </li>
          <li>
            <strong>FastAPI</strong>
            <span>Validation · deterministic identity · bounded source connectors</span>
          </li>
          <li>
            <strong>PostgreSQL + private artifacts</strong>
            <span>Registration UUIDs · aliases · source versions · snapshots · issuer links</span>
          </li>
          <li>
            <strong>Official and attributed sources</strong>
            <span>RUES / Socrata · SFC / RNVE · BVC · La República fallback</span>
          </li>
        </ol>
        <p>
          Browsers call this application’s API. The server handles source credentials, retrieval and
          persistence. Public evidence is separated from private audit payloads and downloaded
          files.
        </p>
      </section>
      <section aria-labelledby="workflow-title">
        <h2 id="workflow-title">Technical workflow</h2>
        {workflows.map((item) => (
          <details className="panel workflow-detail" key={item.title} open>
            <summary>{item.title}</summary>
            <p>{item.body}</p>
            <p>{item.detail}</p>
          </details>
        ))}
      </section>
      <section className="notice">
        <strong>Scope and limits</strong>
        <p>
          Missing evidence stays unknown. RUES does not supply municipality/department in the
          verified schema. Ownership, financial condition, acquisitions, procurement, fiscal
          screening and AI briefings are not implemented. Publisher access, schema changes,
          incomplete imports and ambiguous identity can limit results independently.
        </p>
      </section>
    </section>
  )
}
