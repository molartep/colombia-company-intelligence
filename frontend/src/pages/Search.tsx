import { formatNumber } from '../i18n/format'
import { uiMessage, ruesSearchErrorMessage } from '../i18n/messages'
import { t, useLanguage } from '../i18n'
import { useState } from 'react'
import { AdvancedFilters, FilterHelp } from '../components/AdvancedFilters'
import { readFilters, filterParams, searchKey } from '../api/filters'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { Failure, Loading, SearchLoadingDialog, RefreshAlert } from '../components/Feedback'
import { RegistrationStatus } from '../components/RegistrationStatus'
import { SearchForm } from '../components/SearchForm'
import { RegistrationDate } from '../components/FieldValues'

export function Search() {
  useLanguage()

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
        <h1 className="sr-only">{t('search.companySearch')}</h1>
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
          <div className="bvc-search-filter">
            <label>
              <input
                type="checkbox"
                checked={draftFilters.registered_bvc === 'true'}
                disabled={results.isFetching}
                onChange={(event) =>
                  setDraftFilters({
                    ...draftFilters,
                    registered_bvc: event.target.checked ? 'true' : '',
                  })
                }
              />{' '}
              {t('search.registradoBvc')}
            </label>
            <FilterHelp
              label={t('search.registradoBvc')}
              text={t('search.findsMatchingIssuersInTheRnveDirectoryRetrievesTheirSecurities')}
            />
          </div>
          <AdvancedFilters
            values={draftFilters}
            onChange={setDraftFilters}
            disabled={results.isFetching}
          />
        </SearchForm>
        <div className="source-line">
          <span className="mini-icon" aria-hidden="true">
            ✓
          </span>{' '}
          {t('search.poweredByRuesConfecamaras')} <span>{t('search.viaDatosGovCo')}</span>
        </div>
      </section>
      {q.length >= 2 ? (
        <section className="results" aria-label={t('search.searchResults')}>
          <div className="section-heading">
            <div>
              <p className="eyebrow">{t('search.companyDirectory')}</p>
              <h2>{t('search.searchResults')}</h2>
            </div>
            {results.data && (
              <span className="muted" aria-live="polite">
                {' '}
                {t('common.records', {
                  count: results.data.items.length,
                  more: results.data.has_more ? '+' : '',
                })}
              </span>
            )}
          </div>
          {results.isFetching && (
            <>
              <div className="search-loading-inline">
                <Loading />
              </div>
              <SearchLoadingDialog />
            </>
          )}
          {results.isError && (
            <Failure
              error={results.error}
              message={ruesSearchErrorMessage(results.error)}
              retry={() => void results.refetch()}
            />
          )}
          {results.data && (
            <>
              {results.data.warning && !results.data.stale && (
                <p className="notice" role="status">
                  {uiMessage(results.data.warning)}
                </p>
              )}
              {results.data.stale && (
                <RefreshAlert
                  refresh={() => void results.refetch()}
                  refreshing={results.isFetching}
                >
                  {uiMessage(results.data.warning)}
                </RefreshAlert>
              )}
              {results.data.items.length === 0 ? (
                <div className="empty">
                  <span aria-hidden="true">⌕</span>
                  <h3>{t('search.noMatchingRegistrations')}</h3>
                  <p>
                    {params.get('registered_bvc') === 'true'
                      ? t(
                          'search.noVerifiedBvcRegistrationsMatchThisSearchRnveRegistrationEvidence',
                        )
                      : t('search.tryAShorterPartOfTheLegalNameOrCheck')}
                  </p>
                </div>
              ) : (
                <>
                  <p className="table-scroll-hint" id="search-scroll-hint">
                    {t('common.scrollTable')}
                  </p>
                  <div
                    className="table-wrap search-table-wrap"
                    aria-describedby="search-scroll-hint"
                    role="region"
                    aria-label={t('search.companySearchResultsTable')}
                    tabIndex={0}
                  >
                    <table className="search-table">
                      <colgroup>
                        <col />
                        <col className="nit-column" />
                        <col className="status-column" />
                        <col className="date-column" />
                        <col className="date-column" />
                        <col className="bvc-column" />
                        <col className="profile-column" />
                      </colgroup>
                      <thead>
                        <tr>
                          <th scope="col">{t('search.legalEntity')}</th>
                          <th scope="col">NIT</th>
                          <th scope="col">{t('search.registrationStatus')}</th>
                          <th scope="col">{t('search.registrationDate')}</th>
                          <th scope="col">{t('search.renewalDate')}</th>
                          <th scope="col">{t('search.registradoBvc')}</th>
                          <th>
                            <span className="sr-only">{t('search.openProfile')}</span>
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
                                {company.chamber ?? t('search.chamberMissing')}{' '}
                                {t('search.matricula')}{' '}
                                {company.registration_number ?? t('fields.missing')}
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
                            <td className="bvc-check-cell">
                              {company.registered_bvc && (
                                <span
                                  className="bvc-check"
                                  role="img"
                                  aria-label={t('search.registradoBvc')}
                                  title={t('search.accionesOrdinariasBvc')}
                                >
                                  ✓
                                </span>
                              )}
                            </td>
                            <td>
                              <Link
                                className="profile-open-link"
                                aria-label={t('search.viewValue', { value0: company.legal_name })}
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
              <nav className="pagination" aria-label={t('search.resultPages')}>
                <button
                  disabled={page <= 1}
                  onClick={() => {
                    const next = new URLSearchParams(params)
                    next.set('page', String(page - 1))
                    setParams(next)
                  }}
                >
                  {' '}
                  {t('search.previous')}
                </button>
                <span>
                  {' '}
                  {t('search.page')} {formatNumber(page)}
                </span>
                <button
                  disabled={!results.data.has_more || page >= 100}
                  onClick={() => {
                    const next = new URLSearchParams(params)
                    next.set('page', String(page + 1))
                    setParams(next)
                  }}
                >
                  {' '}
                  {t('search.next')}
                </button>
              </nav>
            </>
          )}
        </section>
      ) : null}
    </>
  )
}
