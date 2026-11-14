import { useState } from 'react'
import { AdvancedFilters } from '../components/AdvancedFilters'
import { readFilters, filterParams, searchKey } from '../api/filters'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { Failure, SearchLoadingDialog } from '../components/Feedback'
import { RegistrationStatus } from '../components/RegistrationStatus'
import { SearchForm } from '../components/SearchForm'
import { RegistrationDate } from '../components/FieldValues'

export function Search() {
  const [params, setParams] = useSearchParams()
  const location = useLocation()
  const queryClient = useQueryClient()
  const navigationState = { returnTo: `/${location.search}` }
  const q = params.get('q') ?? ''
  const filters = filterParams(readFilters(params)).toString()
  const [previousFilters, setPreviousFilters] = useState(filters)
  const [draftFilters, setDraftFilters] = useState(() => readFilters(params))
  if (previousFilters !== filters) {
    setPreviousFilters(filters)
    setDraftFilters(readFilters(params))
  }
  const page = Math.min(100, Math.max(1, Number(params.get('page')) || 1))
  const results = useQuery({
    queryKey: searchKey(q, page, filters),
    queryFn: ({ signal }) => api.search(q, page, signal, filters),
    enabled: q.trim().length >= 2,
    // Restore visited pages without a new request when returning from a profile.
    gcTime: 30 * 60_000,
    refetchOnMount: false,
  })
  return (
    <>
      <section className="hero">
        <h1 className="sr-only">Company search</h1>
        <SearchForm
          initial={q}
          disabled={results.isFetching}
          onSearch={(value) => {
            const nextFilters = filterParams(draftFilters).toString()
            if (value === q && page === 1 && nextFilters === filters) void results.refetch()
            else {
              // Explicit submission refreshes even a previously cached search.
              queryClient.removeQueries({ queryKey: searchKey(value, 1, nextFilters), exact: true })
              const next = new URLSearchParams(nextFilters)
              next.set('q', value)
              next.set('page', '1')
              setParams(next)
            }
          }}
        >
          <AdvancedFilters
            values={draftFilters}
            onChange={setDraftFilters}
            disabled={results.isFetching}
          />
        </SearchForm>
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
          {results.isFetching && <SearchLoadingDialog />}
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
                  <div
                    className="table-wrap search-table-wrap"
                    role="region"
                    aria-label="Company search results table"
                    tabIndex={0}
                  >
                    <table className="search-table">
                      <colgroup>
                        <col />
                        <col className="nit-column" />
                        <col className="status-column" />
                        <col className="date-column" />
                        <col className="date-column" />
                        <col className="profile-column" />
                      </colgroup>
                      <thead>
                        <tr>
                          <th scope="col">Legal entity</th>
                          <th scope="col">NIT</th>
                          <th scope="col">Registration status</th>
                          <th scope="col">Registration date</th>
                          <th scope="col">Renewal date</th>
                          <th>
                            <span className="sr-only">Open profile</span>
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {results.data.items.map((company) => (
                          <tr key={company.id}>
                            <td>
                              <Link
                                className="company-link"
                                to={`/companies/${company.id}`}
                                state={navigationState}
                              >
                                {company.legal_name}
                              </Link>
                              <div className="muted small mt-1">
                                {company.chamber ?? 'Chamber missing'} · Matrícula{' '}
                                {company.registration_number ?? 'missing'}
                              </div>
                              {company.legal_form && (
                                <div className="muted small mt-1">{company.legal_form}</div>
                              )}
                            </td>
                            <td className="nit-cell">
                              {company.nit ?? ''}
                              {company.nit && company.verification_digit
                                ? `-${company.verification_digit}`
                                : ''}
                            </td>
                            <td className="status-cell">
                              <RegistrationStatus status={company.registration_status} />
                            </td>
                            <td className="date-cell">
                              <RegistrationDate value={company.registration_date} blankIfMissing />
                            </td>
                            <td className="date-cell">
                              <RegistrationDate value={company.renewal_date} blankIfMissing />
                            </td>
                            <td>
                              <Link
                                aria-label={`View ${company.legal_name}`}
                                to={`/companies/${company.id}`}
                                state={navigationState}
                              >
                                ↗
                              </Link>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
              <nav className="pagination" aria-label="Result pages">
                <button
                  disabled={page <= 1}
                  onClick={() => {
                    const next = new URLSearchParams(params)
                    next.set('page', String(page - 1))
                    setParams(next)
                  }}
                >
                  ← Previous
                </button>
                <span>Page {page}</span>
                <button
                  disabled={!results.data.has_more || page >= 100}
                  onClick={() => {
                    const next = new URLSearchParams(params)
                    next.set('page', String(page + 1))
                    setParams(next)
                  }}
                >
                  Next →
                </button>
              </nav>
            </>
          )}
        </section>
      ) : null}
    </>
  )
}
