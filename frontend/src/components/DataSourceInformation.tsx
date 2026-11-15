import { SourceInformationCard } from './SourceInformationCard'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Profile } from '../types'
import { label } from '../utils'
import { Failure, Loading } from './Feedback'
import { MissingValue, TimestampValue } from './FieldValues'

export function DataSourceInformation({
  company,
  refresh,
  refreshing = false,
}: {
  company: Profile
  refresh?: () => void
  refreshing?: boolean
}) {
  const records = useQuery({
    queryKey: ['records', company.id],
    queryFn: ({ signal }) => api.sources(company.id, signal),
  })
  return (
    <SourceInformationCard title="Data Source Information" id="data-source-information">
      {refresh && (
        <button
          type="button"
          className="refresh-button source-refresh"
          disabled={refreshing}
          aria-busy={refreshing}
          onClick={refresh}
        >
          {refreshing ? 'Refreshing…' : 'Refresh data'}
        </button>
      )}
      <p className="muted source-introduction">
        Where this profile comes from, when it was retrieved, and which fields the source provides.
      </p>
      <div className="source-providers">
        {company.sources.map((source) => (
          <section className="source-provider" key={source.id} aria-label={source.name}>
            <div className="source-provider-heading">
              <h3>{source.name}</h3>
              <p className="source-availability small">
                Availability: {label(source.availability)}
                <span
                  className={`availability-dot availability-dot--${source.availability === 'available' ? 'available' : 'unavailable'}`}
                  aria-hidden="true"
                />
              </p>
            </div>
            <p className="small muted">{source.description}</p>
            <a className="text-link" href={source.dataset_url} target="_blank" rel="noreferrer">
              Open official dataset ↗
            </a>
          </section>
        ))}
        {!company.sources.length && (
          <p className="small muted">Source metadata is not available for this profile.</p>
        )}
      </div>
      <section className="source-freshness" aria-labelledby="source-freshness-title">
        <h3 id="source-freshness-title">Data freshness</h3>
        <dl>
          <div>
            <dt>Retrieved by this application</dt>
            <dd>
              <TimestampValue value={company.retrieved_at} />
            </dd>
          </div>
          <div>
            <dt>Record updated in RUES</dt>
            <dd>
              <TimestampValue value={company.source_updated_at} rues />
            </dd>
          </div>
          <div>
            <dt>Official dataset updated</dt>
            <dd>
              <TimestampValue value={company.dataset_updated_at} />
            </dd>
          </div>
        </dl>
        <p className="small muted">
          Retrieval is when we saved this record. The record and dataset update dates are reported
          separately by the source.
        </p>
      </section>
      <details className="source-disclosure">
        <summary>Attribute availability & provenance</summary>
        <p className="small muted">
          Present fields are backed by this registration record. Missing fields were not supplied;
          not yet checked means no finding has been made.
        </p>
        <dl className="source-attributes">
          {Object.entries(company.attributes).map(([key, state]) => (
            <div key={key}>
              <dt>{label(key)}</dt>
              <dd>
                {state.state === 'present' ? (
                  <span className="badge value-pill--present">Present</span>
                ) : state.state === 'missing_from_record' ? (
                  <MissingValue />
                ) : (
                  <span className="badge value-pill--muted">{label(state.state)}</span>
                )}
                {state.source_field && (
                  <small className="block muted">
                    Source field: <code>{state.source_field}</code>
                  </small>
                )}
                {state.note && <small className="block muted">{state.note}</small>}
                {state.record_id && (
                  <a className="small text-link" href={`#source-record-${state.record_id}`}>
                    Supporting record ↓
                  </a>
                )}
              </dd>
            </div>
          ))}
        </dl>
      </details>
      <section className="source-records" aria-labelledby="source-records-title">
        <h3 id="source-records-title">Supporting records</h3>
        {records.isPending && <Loading />}
        {records.isError && <Failure error={records.error} retry={() => void records.refetch()} />}
        {records.data?.length === 0 && (
          <p className="small muted">No supporting records are available to display.</p>
        )}
        {records.data?.map((record, index) => (
          <details className="source-disclosure" key={record.id} id={`source-record-${record.id}`}>
            <summary>
              Registration record{records.data.length > 1 ? ` ${index + 1}` : ''} ·{' '}
              {company.sources.find((source) => source.id === record.source_id)?.name ??
                record.source_id}
            </summary>
            <dl>
              <div>
                <dt>Source row ID</dt>
                <dd>{record.external_record_id || <MissingValue />}</dd>
              </div>
              <div>
                <dt>Retrieved</dt>
                <dd>
                  <TimestampValue value={record.retrieved_at} />
                </dd>
              </div>
              <div>
                <dt>Record updated</dt>
                <dd>
                  <TimestampValue value={record.source_updated_at} rues />
                </dd>
              </div>
              <div>
                <dt>Payload SHA-256</dt>
                <dd className="hash">{record.payload_hash}</dd>
              </div>
            </dl>
            <details className="record-fields">
              <summary>Public fields & field mappings</summary>
              <h4>Field mappings</h4>
              <dl>
                {Object.entries(record.field_mapping).map(([attribute, field]) => (
                  <div key={attribute}>
                    <dt>{label(attribute)}</dt>
                    <dd>
                      <code>{field}</code>
                    </dd>
                  </div>
                ))}
              </dl>
              <h4>Original public fields</h4>
              <dl>
                {Object.entries(record.fields).map(([key, value]) => (
                  <div key={key}>
                    <dt>{key}</dt>
                    <dd>{value || <MissingValue />}</dd>
                  </div>
                ))}
              </dl>
            </details>
            {record.source_url && (
              <a className="text-link" href={record.source_url} target="_blank" rel="noreferrer">
                View originating dataset ↗
              </a>
            )}
          </details>
        ))}
        <p className="small muted source-privacy-note">
          Only public registration fields are shown. Personal identifiers and representative details
          are excluded from these records.
        </p>
      </section>
    </SourceInformationCard>
  )
}
