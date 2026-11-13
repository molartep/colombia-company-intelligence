import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { Failure, Loading } from '../components/Feedback'
import { dateTime, label } from '../utils'

export function CompanyProfile() {
  const { id = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') === 'sources' ? 'sources' : 'overview'
  const [copyStatus, setCopyStatus] = useState('')
  const company = useQuery({
    queryKey: ['company', id],
    queryFn: ({ signal }) => api.profile(id, signal),
  })
  const records = useQuery({
    queryKey: ['records', id],
    queryFn: ({ signal }) => api.sources(id, signal),
    enabled: tab === 'sources',
  })
  if (company.isPending) return <Loading />
  if (company.isError) return <Failure error={company.error} retry={() => void company.refetch()} />
  const data = company.data
  return (
    <section className="profile">
      <Link className="back-link" to="/">
        ← Company search
      </Link>
      <div className="profile-heading">
        <div>
          <p className="eyebrow">REGISTRATION PROFILE</p>
          <h1>{data.legal_name}</h1>
          <div className="identity-line">
            <span>
              NIT {data.nit ?? 'missing from record'}
              {data.verification_digit ? `-${data.verification_digit}` : ''}
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
            <span className="badge">{data.registration_status ?? 'Status missing'}</span>
            <span role="status" className="small">
              {copyStatus}
            </span>
          </div>
        </div>
        <span className="source-seal">
          RUES
          <br />
          <small>OFFICIAL SOURCE</small>
        </span>
      </div>
      <div className="notice">
        {data.resolution_note}
        {data.conflicting_registration_count > 0 && (
          <p>
            {data.conflicting_registration_count} other cached registration(s) share this NIT.
            Identity requires review.
          </p>
        )}
      </div>
      <nav className="tabs" aria-label="Company sections">
        <Link
          aria-current={tab === 'overview' ? 'page' : undefined}
          to="?tab=overview"
          onClick={(event) => {
            event.preventDefault()
            setParams({ tab: 'overview' })
          }}
        >
          Overview
        </Link>
        <Link aria-current={tab === 'sources' ? 'page' : undefined} to="?tab=sources">
          Sources
        </Link>
        <span>
          Financials <small>Coming later</small>
        </span>
        <span>
          Corporate events <small>Coming later</small>
        </span>
        <span>
          Screening <small>Coming later</small>
        </span>
      </nav>
      {tab === 'overview' ? (
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
                  Department: data.department,
                  Municipality: data.municipality,
                }).map(([key, value]) => (
                  <div key={key}>
                    <dt>{key}</dt>
                    <dd>
                      {value ??
                        (key === 'Department' || key === 'Municipality'
                          ? 'Unavailable in source'
                          : 'Missing from record')}
                    </dd>
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
                    <dd>{value ?? 'Missing from record'}</dd>
                  </div>
                ))}
              </dl>
              <p className="small muted mt-4">
                Dates are shown in their original source format (typically YYYYMMDD). No geographic
                inference is made from the chamber.
              </p>
            </article>
          </div>
          <article className="panel freshness">
            <h2>Evidence & freshness</h2>
            <dl>
              <div>
                <dt>Retrieved by this application</dt>
                <dd>{dateTime(data.retrieved_at)}</dd>
              </div>
              <div>
                <dt>Record updated in RUES</dt>
                <dd>{dateTime(data.source_updated_at)}</dd>
              </div>
              <div>
                <dt>Official dataset updated</dt>
                <dd>{dateTime(data.dataset_updated_at)}</dd>
              </div>
            </dl>
            <p className="small muted">
              These timestamps describe different events. A recent retrieval does not mean the
              underlying registration is recent.
            </p>
          </article>
          <details className="panel">
            <summary>Attribute availability & provenance</summary>
            <dl>
              {Object.entries(data.attributes).map(([key, state]) => (
                <div key={key}>
                  <dt>{label(key)}</dt>
                  <dd>
                    {label(state.state)}
                    {state.source_field && (
                      <small className="block muted">{state.source_field}</small>
                    )}
                    {state.note && <small className="block">{state.note}</small>}
                  </dd>
                </div>
              ))}
            </dl>
          </details>
        </>
      ) : (
        <div className="sources-section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">AUDITABLE BY DESIGN</p>
              <h2>Records & provenance</h2>
            </div>
          </div>
          {data.sources.map((source) => (
            <article className="panel" key={source.id}>
              <h3>{source.name}</h3>
              <p className="muted">{source.description}</p>
              <p className="mt-4">Availability: {label(source.availability)}</p>
              <a className="text-link" href={source.dataset_url} target="_blank" rel="noreferrer">
                Open official dataset ↗
              </a>
            </article>
          ))}
          {records.isPending && <Loading />}
          {records.isError && (
            <Failure error={records.error} retry={() => void records.refetch()} />
          )}
          {records.data?.map((record) => (
            <article className="panel" key={record.id}>
              <div className="section-heading">
                <h3>Registration record</h3>
                <span className="badge">RUES</span>
              </div>
              <dl>
                <div>
                  <dt>Source row ID</dt>
                  <dd>{record.external_record_id}</dd>
                </div>
                <div>
                  <dt>Retrieved</dt>
                  <dd>{dateTime(record.retrieved_at)}</dd>
                </div>
                <div>
                  <dt>Record updated</dt>
                  <dd>{dateTime(record.source_updated_at)}</dd>
                </div>
                <div>
                  <dt>Payload SHA-256</dt>
                  <dd className="hash">{record.payload_hash}</dd>
                </div>
              </dl>
              <details>
                <summary>Public fields & field mappings</summary>
                <dl>
                  {Object.entries(record.fields).map(([key, value]) => (
                    <div key={key}>
                      <dt>{key}</dt>
                      <dd>{value}</dd>
                    </div>
                  ))}
                </dl>
              </details>
              {record.source_url && (
                <a className="text-link" href={record.source_url} target="_blank" rel="noreferrer">
                  View originating dataset ↗
                </a>
              )}
              <p className="small muted mt-4">
                Personal identifiers and representative details are excluded from this view. The
                source row ID identifies the originating record.
              </p>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
