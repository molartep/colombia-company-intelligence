import { uiMessage } from '../i18n/messages'
import { t, useLanguage } from '../i18n'
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
  useLanguage()

  const records = useQuery({
    queryKey: ['records', company.id],
    queryFn: ({ signal }) => api.sources(company.id, signal),
  })
  return (
    <SourceInformationCard
      title={t('provenance.dataSourceInformation')}
      id="data-source-information"
    >
      {refresh && (
        <button
          type="button"
          className="refresh-button source-refresh"
          disabled={refreshing}
          aria-busy={refreshing}
          onClick={refresh}
        >
          {refreshing ? t('provenance.refreshing') : t('provenance.refreshData')}
        </button>
      )}
      <p className="muted source-introduction">
        {' '}
        {t('provenance.whereThisProfileComesFromWhenItWasRetrievedAnd')}
      </p>
      <div className="source-providers">
        {company.sources.map((source) => (
          <section className="source-provider" key={source.id} aria-label={uiMessage(source.name)}>
            <div className="source-provider-heading">
              <h3>{uiMessage(source.name)}</h3>
              <p className="source-availability small">
                {' '}
                {t('provenance.availability')} {label(source.availability)}
                <span
                  className={`availability-dot availability-dot--${source.availability === 'available' ? 'available' : 'unavailable'}`}
                  aria-hidden="true"
                />
              </p>
            </div>
            <p className="small muted">{uiMessage(source.description)}</p>
            <a className="text-link" href={source.dataset_url} target="_blank" rel="noreferrer">
              {' '}
              {t('provenance.openOfficialDataset')}
            </a>
          </section>
        ))}
        {!company.sources.length && (
          <p className="small muted">
            {' '}
            {t('provenance.sourceMetadataIsNotAvailableForThisProfile')}
          </p>
        )}
      </div>
      <section className="source-freshness" aria-labelledby="source-freshness-title">
        <h3 id="source-freshness-title">{t('provenance.dataFreshness')}</h3>
        <dl>
          <div>
            <dt>{t('provenance.retrievedByThisApplication')}</dt>
            <dd>
              <TimestampValue value={company.retrieved_at} />
            </dd>
          </div>
          <div>
            <dt>{t('provenance.recordUpdatedInRues')}</dt>
            <dd>
              <TimestampValue value={company.source_updated_at} rues />
            </dd>
          </div>
          <div>
            <dt>{t('provenance.officialDatasetUpdated')}</dt>
            <dd>
              <TimestampValue value={company.dataset_updated_at} />
            </dd>
          </div>
        </dl>
        <p className="small muted">
          {' '}
          {t('provenance.retrievalIsWhenWeSavedThisRecordTheRecordAnd')}
        </p>
      </section>
      <details className="source-disclosure">
        <summary>{t('provenance.attributeAvailabilityProvenance')}</summary>
        <p className="small muted">
          {' '}
          {t('provenance.presentFieldsAreBackedByThisRegistrationRecordMissingFields')}
        </p>
        <dl className="source-attributes">
          {Object.entries(company.attributes).map(([key, state]) => (
            <div key={key}>
              <dt>{label(key)}</dt>
              <dd>
                {state.state === 'present' ? (
                  <span className="badge value-pill--present">{t('provenance.present')}</span>
                ) : state.state === 'missing_from_record' ? (
                  <MissingValue />
                ) : (
                  <span className="badge value-pill--muted">{label(state.state)}</span>
                )}
                {state.source_field && (
                  <small className="block muted">
                    {' '}
                    {t('provenance.sourceField')} <code>{state.source_field}</code>
                  </small>
                )}
                {state.note && <small className="block muted">{uiMessage(state.note)}</small>}
                {state.record_id && (
                  <a className="small text-link" href={`#source-record-${state.record_id}`}>
                    {' '}
                    {t('provenance.supportingRecord')}
                  </a>
                )}
              </dd>
            </div>
          ))}
        </dl>
      </details>
      <section className="source-records" aria-labelledby="source-records-title">
        <h3 id="source-records-title">{t('provenance.supportingRecords')}</h3>
        {records.isPending && <Loading />}
        {records.isError && <Failure error={records.error} retry={() => void records.refetch()} />}
        {records.data?.length === 0 && (
          <p className="small muted"> {t('provenance.noSupportingRecordsAreAvailableToDisplay')}</p>
        )}
        {records.data?.map((record, index) => (
          <details className="source-disclosure" key={record.id} id={`source-record-${record.id}`}>
            <summary>
              {' '}
              {t('provenance.registrationRecord')} {records.data.length > 1 ? ` ${index + 1}` : ''}{' '}
              ·{' '}
              {uiMessage(
                company.sources.find((source) => source.id === record.source_id)?.name ??
                  record.source_id,
              )}
            </summary>
            <dl>
              <div>
                <dt>{t('provenance.sourceRowId')}</dt>
                <dd>{record.external_record_id || <MissingValue />}</dd>
              </div>
              <div>
                <dt>{t('provenance.retrieved')}</dt>
                <dd>
                  <TimestampValue value={record.retrieved_at} />
                </dd>
              </div>
              <div>
                <dt>{t('provenance.recordUpdated')}</dt>
                <dd>
                  <TimestampValue value={record.source_updated_at} rues />
                </dd>
              </div>
              <div>
                <dt>{t('provenance.payloadSha256')}</dt>
                <dd className="hash">{record.payload_hash}</dd>
              </div>
            </dl>
            <details className="record-fields">
              <summary>{t('provenance.publicFieldsFieldMappings')}</summary>
              <h4>{t('provenance.fieldMappings')}</h4>
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
              <h4>{t('provenance.originalPublicFields')}</h4>
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
                {' '}
                {t('provenance.viewOriginatingDataset')}
              </a>
            )}
          </details>
        ))}
        <p className="small muted source-privacy-note">
          {' '}
          {t('provenance.onlyPublicRegistrationFieldsAreShownPersonalIdentifiersAndRepresentative')}
        </p>
      </section>
    </SourceInformationCard>
  )
}
