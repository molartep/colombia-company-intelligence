import { Screening } from '../components/Screening'
import { DataSourceInformation } from '../components/DataSourceInformation'
import { CapitalMarkets } from '../components/CapitalMarkets'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { Failure, Loading, RefreshAlert } from '../components/Feedback'
import { label, searchReturnPath } from '../utils'
import { RegistrationStatus } from '../components/RegistrationStatus'
import { MissingValue, RegistrationDate } from '../components/FieldValues'

export function CompanyProfile() {
  const { id = '' } = useParams()
  const [params] = useSearchParams()
  const location = useLocation()
  const returnTo = searchReturnPath(location.state)
  const tab = ['capital-markets', 'screening'].includes(params.get('tab') ?? '')
    ? params.get('tab')
    : 'overview'
  const [copyStatus, setCopyStatus] = useState('')
  const client = useQueryClient()
  const refresh = useMutation({
    mutationFn: () => api.profile(id, undefined, true),
    onSuccess: async (data) => {
      client.setQueryData(['company', id], data)
      await client.invalidateQueries({ queryKey: ['records', id] })
    },
  })
  const company = useQuery({
    queryKey: ['company', id],
    queryFn: ({ signal }) => api.profile(id, signal),
  })
  if (company.isPending) return <Loading />
  if (company.isError) return <Failure error={company.error} retry={() => void company.refetch()} />
  const data = company.data
  return (
    <section className="profile">
      <Link className="back-link" to={returnTo}>
        ← Company search
      </Link>
      <div className="profile-heading">
        <div>
          <h1>{data.legal_name}</h1>
          <div className="identity-line">
            <span className="profile-nit">
              NIT:{' '}
              {data.nit ? (
                <span>
                  {data.nit}
                  {data.verification_digit ? `-${data.verification_digit}` : ''}
                </span>
              ) : (
                <MissingValue />
              )}
            </span>
            {data.nit && (
              <button
                className="copy"
                aria-label="Copy NIT"
                onClick={() => {
                  void navigator.clipboard.writeText(data.nit ?? '').then(
                    () => setCopyStatus('NIT copied'),
                    () => setCopyStatus('Could not copy NIT'),
                  )
                }}
              >
                Copy
              </button>
            )}
            <span role="status" className="small">
              {copyStatus}
            </span>
          </div>
          <div className="profile-status">
            Status:{' '}
            {data.registration_status?.trim() ? (
              <RegistrationStatus status={data.registration_status} />
            ) : (
              <MissingValue />
            )}
          </div>
        </div>
      </div>
      <nav className="tabs" aria-label="Company sections">
        <Link
          aria-current={tab === 'overview' ? 'page' : undefined}
          to="?tab=overview"
          state={{ returnTo }}
        >
          Overview
        </Link>
        <Link
          aria-current={tab === 'capital-markets' ? 'page' : undefined}
          to="?tab=capital-markets"
          state={{ returnTo }}
        >
          Capital Markets
        </Link>
        <span>
          Financials <small>Coming later</small>
        </span>
        <span>
          Corporate events <small>Coming later</small>
        </span>
        <Link
          aria-current={tab === 'screening' ? 'page' : undefined}
          to="?tab=screening"
          state={{ returnTo }}
        >
          Government Contracts
        </Link>
      </nav>
      {tab === 'screening' ? (
        <Screening key={id} companyId={id} />
      ) : tab === 'capital-markets' ? (
        <CapitalMarkets companyId={id} />
      ) : (
        <>
          <div className="profile-grid">
            <article className="panel">
              <p className="eyebrow">VERIFIED SOURCE FIELDS</p>
              <h2>Company identity</h2>
              <dl>
                {Object.entries({
                  'Legal name': data.legal_name,
                  'Legal organization': data.legal_form,
                  'Primary CIIU code': data.primary_ciiu,
                }).map(([key, value]) => (
                  <div key={key}>
                    <dt>{key}</dt>
                    <dd>{value?.trim() ? value : <MissingValue />}</dd>
                  </div>
                ))}
              </dl>
            </article>
            <article className="panel">
              <p className="eyebrow">BUSINESS REGISTRY</p>
              <h2>Registration details</h2>
              <dl>
                {Object.entries(data.registration).map(([key, value]) => (
                  <div key={key}>
                    <dt>{label(key)}</dt>
                    <dd>
                      {key.endsWith('_date') ? (
                        <RegistrationDate value={value} />
                      ) : value?.trim() ? (
                        value
                      ) : (
                        <MissingValue />
                      )}
                    </dd>
                  </div>
                ))}
              </dl>
            </article>
          </div>
          {(refresh.isError ||
            data.sources.some((source) => source.availability === 'failed_to_retrieve')) && (
            <RefreshAlert refresh={() => refresh.mutate()} refreshing={refresh.isPending}>
              {refresh.error?.message ??
                'The source was unavailable at the last check. Previously retrieved data is preserved.'}
            </RefreshAlert>
          )}
          {refresh.isSuccess && (
            <p className="small muted" role="status">
              Registration refreshed from the official source.
            </p>
          )}
          <DataSourceInformation
            company={data}
            refresh={() => refresh.mutate()}
            refreshing={refresh.isPending}
          />
        </>
      )}
    </section>
  )
}
