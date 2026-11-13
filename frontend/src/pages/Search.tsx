import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { Failure, Loading } from '../components/Feedback'
import { label } from '../utils'
import { SearchForm } from '../components/SearchForm'

export function Search() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const page = Math.min(100, Math.max(1, Number(params.get('page')) || 1))
  const results = useQuery({
    queryKey: ['search', q, page],
    queryFn: ({ signal }) => api.search(q, page, signal),
    enabled: q.trim().length >= 2,
  })
  return (
    <>
      <section className="hero">
        <div className="eyebrow">
          <span className="status-dot" /> OFFICIAL DATA. TRACEABLE EVIDENCE.
        </div>
        <h1>
          A clearer view of
          <br />
          <em>Colombian companies.</em>
        </h1>
        <p className="hero-description">
          Start with identity. Find registration records, resolve a legal name, and understand the
          source behind every result.
        </p>
        <SearchForm initial={q} onSearch={(value) => setParams({ q: value, page: '1' })} />
        <div className="source-line">
          <span className="mini-icon">✓</span> Powered by RUES / Confecámaras{' '}
          <span>via datos.gov.co</span>
        </div>
      </section>
      {q.length >= 2 ? (
        <section className="results" aria-label="Search results">
          <div className="section-heading">
            <div>
              <p className="eyebrow">COMPANY DIRECTORY</p>
              <h2>Search results</h2>
            </div>
            <span className="muted">Page {page} · up to 20 records</span>
          </div>
          {results.isPending && <Loading />}
          {results.isError && (
            <Failure error={results.error} retry={() => void results.refetch()} />
          )}
          {results.data && (
            <>
              {results.data.stale && (
                <div className="notice warning" role="status">
                  {results.data.warning}
                </div>
              )}
              {results.data.items.length === 0 ? (
                <div className="empty">
                  <span aria-hidden="true">⌕</span>
                  <h3>No matching registrations</h3>
                  <p>
                    Try a shorter part of the legal name or check the NIT. This is a bounded search
                    of one public dataset, not proof a company does not exist.
                  </p>
                </div>
              ) : (
                <>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Legal identity</th>
                          <th>Registration status</th>
                          <th>Location</th>
                          <th>Match / source</th>
                          <th>
                            <span className="sr-only">Open profile</span>
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {results.data.items.map((company) => (
                          <tr key={company.id}>
                            <td>
                              <Link className="company-link" to={`/companies/${company.id}`}>
                                {company.legal_name}
                              </Link>
                              <div className="muted small">
                                NIT {company.nit ?? 'missing from record'}
                                {company.verification_digit ? `-${company.verification_digit}` : ''}
                              </div>
                              <div className="muted small mt-1">
                                {company.chamber ?? 'Chamber missing'} · Matrícula{' '}
                                {company.registration_number ?? 'missing'}
                              </div>
                              {company.legal_form && (
                                <div className="muted small mt-1">{company.legal_form}</div>
                              )}
                            </td>
                            <td>
                              <span className="badge">
                                {company.registration_status ?? 'Missing from record'}
                              </span>
                            </td>
                            <td className="muted">
                              {[company.municipality, company.department]
                                .filter(Boolean)
                                .join(', ') || 'Unavailable in source'}
                            </td>
                            <td>
                              <span className="match">{label(company.match_type)}</span>
                              <div className="small muted">RUES · Confecámaras</div>
                            </td>
                            <td>
                              <Link
                                aria-label={`View ${company.legal_name}`}
                                to={`/companies/${company.id}`}
                              >
                                ↗
                              </Link>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="small muted mt-4">
                    Ranked within this page. Separate registrations may share a NIT; review each
                    record before selecting an entity.
                  </p>
                </>
              )}
              <nav className="pagination" aria-label="Result pages">
                <button
                  disabled={page <= 1}
                  onClick={() => setParams({ q, page: String(page - 1) })}
                >
                  ← Previous
                </button>
                <span>Page {page}</span>
                <button
                  disabled={!results.data.has_more || page >= 100}
                  onClick={() => setParams({ q, page: String(page + 1) })}
                >
                  Next →
                </button>
              </nav>
            </>
          )}
        </section>
      ) : (
        <section className="principles">
          <article>
            <span>01 / IDENTITY FIRST</span>
            <h3>Find the right registration</h3>
            <p>
              Search by NIT or legal name. Compare records without automatically merging similar
              entities.
            </p>
          </article>
          <article>
            <span>02 / EVIDENCE INCLUDED</span>
            <h3>Go directly to the source</h3>
            <p>
              Every profile connects to official records, retrieval dates, and transparent field
              mappings.
            </p>
          </article>
          <article>
            <span>03 / CLEAR LIMITATIONS</span>
            <h3>Know what’s still unknown</h3>
            <p>
              Missing information is marked clearly. Financials, listings, and screening have not
              yet been checked.
            </p>
          </article>
        </section>
      )}
    </>
  )
}
