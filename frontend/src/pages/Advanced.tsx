import { ArchitectureDiagram, WorkflowDiagram } from '../components/PlatformDiagrams'
import { FilterHelp } from '../components/AdvancedFilters'
import { uiMessage } from '../i18n/messages'
import { formatNumber } from '../i18n/format'
import { label } from '../utils'
import { t, useLanguage } from '../i18n'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { DirectoryImport } from '../components/DirectoryImport'
import { Failure, Loading } from '../components/Feedback'
import { dateTime } from '../utils'

const workflows = () => [
  {
    title: t('advanced.1SearchAndRegistrationIdentity'),
    body: t('advanced.submittingSearchSendsGetApiV1CompaniesWithANit'),
    detail: t('advanced.eachOfficialRegistrationRowHasItsOwnPersistedUuidKeyed'),
  },
  {
    title: t('advanced.2PersistenceProvenanceAndOutageFallback'),
    body: t('advanced.searchResultsAreUpsertedIntoPostgresUsingSqlalchemyCompaniesAnd'),
    detail: t('advanced.httpxAppliesBoundedRetriesAndConcurrencyIfAnOfficialSource'),
  },
  {
    title: t('advanced.3DirectoryImportAndConservativeReconciliation'),
    body: t('advanced.theImportActionOpensAFreshServerSideBrowserVisits'),
    detail: t('advanced.theExistingParserRejectsOversizedArchivesFormulasMacrosExternalWorkbook'),
  },
  {
    title: t('advanced.4RegistradoBvcDiscoveryBeforePagination'),
    body: t('advanced.theBvcCheckboxSearchesTheImportedIssuerDirectoryForCandidate'),
    detail: t('advanced.aVerifiedIndicatorRequiresAVerifiedIssuerRelationshipAndOrdinary'),
  },
  {
    title: t('advanced.5CapitalMarketsRetrievalAndQuoteFallback'),
    body: t('advanced.openingCapitalMarketsForAVerifiedIssuerRetrievesMissingOr'),
    detail: t('advanced.quoteResolutionTriesBvcThenLaRepublicaThenOfficialSfc'),
  },
  {
    title: t('advanced.secopWorkflow.title'),
    body: t('advanced.secopWorkflow.body'),
    detail: t('advanced.secopWorkflow.detail'),
  },
  {
    title: t('advanced.6RuntimeBoundariesAndAdministration'),
    body: t('advanced.theLocalViteServerServesReactAndProxiesRelativeApi'),
    detail: t('advanced.importsArePostOperationsWithA10MibStreamedUpload'),
  },
]

const dependencies = (): Record<string, string> => ({
  sfc_rnve: t('advanced.initialDirectoryImportUsedByBvcSearchAndAllIssuer'),
  sfc_rnve_issuer_details: t('advanced.onDemandAfterAVerifiedIssuerLinkNoSeparateImport'),
  sfc_rnve_securities: t('advanced.onDemandForDiscoveredVerifiedIssuersNoBulkImportRequired'),
  bvc_listings: t('advanced.verifiedOrdinaryShareIdentityAndConfiguredPublicPageLocatorPublisher'),
  la_republica_stock_directory: t('advanced.fetchedAutomaticallyOnDemandPersistedFor24HoursUpTo'),
  la_republica_quotes: t(
    'advanced.automaticPublisherDirectoryDiscoveryThenExactIdentityVerificationNoCompany',
  ),
  sfc_daily_quotes: t('advanced.officialDailyPriceFallbackUsingAnExactAnnNotA'),
})

export function Advanced() {
  useLanguage()

  const status = useQuery({ queryKey: ['platform'], queryFn: ({ signal }) => api.platform(signal) })
  const data = status.data
  return (
    <section className="advanced-page">
      <p className="eyebrow">{t('advanced.platformReference')}</p>
      <h1>{t('advanced.advanced')}</h1>
      <p className="parameters-intro">
        {' '}
        {t('advanced.architectureDataReadinessAndTheTechnicalWorkflowBehindEachFinding')}
      </p>
      <section className="panel" aria-labelledby="runtime-status-title">
        <div className="section-heading">
          <h2 id="runtime-status-title">{t('advanced.currentDataState')}</h2>
          <button
            className="refresh-button"
            disabled={status.isFetching}
            onClick={() => void status.refetch()}
          >
            {status.isFetching ? t('advanced.checking') : t('advanced.refreshStatus')}
          </button>
        </div>
        <p className="muted small">
          {' '}
          {t('advanced.databaseObservationsFromThisServerNotLiveUpstreamProbesNot')}
        </p>
        {status.isPending && <Loading />}
        {status.isError && <Failure error={status.error} retry={() => void status.refetch()} />}
        {data && (
          <>
            <p className="small">
              {' '}
              {t('advanced.statusChecked')} {dateTime(data.checked_at)}
            </p>
            <dl className="platform-counts">
              {Object.entries(data.counts).map(([key, value]) => (
                <div key={key}>
                  <dt>
                    <span>{label(key)}</span>
                    <FilterHelp
                      label={label(key)}
                      text={t(`advanced.metricHelp.${key}`, {
                        defaultValue: t('advanced.metricHelp.other'),
                      })}
                    />
                  </dt>
                  <dd>{formatNumber(value)}</dd>
                </div>
              ))}
            </dl>
            {data.directory_missing && (
              <div className="notice warning" role="alert">
                <strong>{t('advanced.rnveDirectoryIsEmpty')}</strong>
                <p> {t('advanced.capitalMarketsIdentityMatchingAndRegistradoBvcSearchNeedThis')}</p>
                <DirectoryImport />
              </div>
            )}
            {data.import_access === 'disabled' && (
              <p className="notice">
                {' '}
                {t('advanced.importsAreDisabledOnThisDeploymentUntilItsAdministratorConfigures')}
              </p>
            )}
            {data.import_access === 'admin_key' && (
              <p className="notice">
                {' '}
                {t('advanced.directoryImportsRequireTheAdministratorKeyInTheImportForm')}
              </p>
            )}
            <div className="table-wrap">
              <table className="platform-sources">
                <thead>
                  <tr>
                    <th>{t('advanced.source')}</th>
                    <th>{t('advanced.currentState')}</th>
                    <th>{t('advanced.lastAttemptSuccess')}</th>
                    <th>{t('advanced.dependencyAndWorkflow')}</th>
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
                        {uiMessage(data.rues.name)} ↗
                      </a>
                    </td>
                    <td>{label(data.rues.availability)}</td>
                    <td>
                      {dateTime(data.rues.last_checked_at)}
                      <br /> {t('advanced.datasetUpdated')} {dateTime(data.rues.last_updated_at)}
                    </td>
                    <td>{t('advanced.liveSearchAndRegistrationRefreshCacheGrowsWithUseNo')}</td>
                  </tr>
                  <tr>
                    <td>{t('advanced.ruesParameterCatalog')}</td>
                    <td>
                      {' '}
                      {t('advanced.bundled')} {formatNumber(data.parameter_options)}{' '}
                      {t('advanced.options')}
                    </td>
                    <td>
                      {' '}
                      {t('advanced.verified')} {dateTime(data.parameter_verified_at)}
                    </td>
                    <td>
                      {' '}
                      {t('advanced.versionedCodeLabelSnapshotShippedWithTheAppIndependentOf')}
                    </td>
                  </tr>
                  <tr>
                    <td>
                      <a
                        className="text-link"
                        href="https://www.datos.gov.co/d/jbjy-vk9h"
                        target="_blank"
                        rel="noreferrer"
                      >
                        {t('advanced.secopReadiness.title')} ↗
                      </a>
                    </td>
                    <td>
                      {data.secop
                        ? t(`advanced.secopReadiness.states.${data.secop.status}`)
                        : t('advanced.secopReadiness.unavailable')}
                      <p className="small">{t('advanced.secopReadiness.scope')}</p>
                    </td>
                    <td>
                      {dateTime(data.secop?.last_attempt_at ?? null)}
                      <br />
                      {t('advanced.success')} {dateTime(data.secop?.last_success_at ?? null)}
                      <br />
                      {t('advanced.datasetUpdated')}{' '}
                      {dateTime(data.secop?.source_updated_at ?? null)}
                    </td>
                    <td>
                      {t('advanced.secopReadiness.dependency')}
                      {data.secop && (
                        <p className="small">
                          {t('advanced.secopReadiness.policy', {
                            hours: formatNumber(data.secop.cache_hours),
                            rows: formatNumber(data.secop.max_rows),
                          })}
                        </p>
                      )}
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
                          {uiMessage(source.name)} ↗
                        </a>
                      </td>
                      <td>
                        {source.id === 'sfc_rnve' && data.directory_missing
                          ? t('advanced.importRequired')
                          : source.last_ingestion_status === 'failed'
                            ? t('advanced.lastAttemptFailed')
                            : !source.last_success_at
                              ? t('advanced.notYetChecked')
                              : source.stale
                                ? t('advanced.staleEvidence')
                                : t('advanced.cachedEvidenceAvailable')}
                        {source.latest_snapshot && (
                          <p className="small">
                            {' '}
                            {t('advanced.observation')}{' '}
                            {dateTime(source.latest_snapshot.observed_at)}
                            <br /> {t('advanced.coverage')}{' '}
                            {source.latest_snapshot.complete_current
                              ? t('advanced.completeCurrentAttestation')
                              : t('advanced.notAttestedComplete')}
                          </p>
                        )}
                        {source.last_error && (
                          <p className="small">
                            {' '}
                            {t('advanced.recordedError')} <code>{source.last_error}</code>
                          </p>
                        )}
                      </td>
                      <td>
                        {dateTime(source.last_attempt_at)}
                        <br /> {t('advanced.success')} {dateTime(source.last_success_at)}
                      </td>
                      <td>
                        {dependencies()[source.id] ??
                          t('advanced.consultTheSourceSpecificEvidenceForScope')}
                        {source.id === 'sfc_rnve' && !data.directory_missing && (
                          <details>
                            <summary>{t('advanced.updateIssuerDirectory')}</summary>
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
        <h2>{t('advanced.architecture')}</h2>
        <ArchitectureDiagram />
      </section>
      <section aria-labelledby="workflow-title">
        <h2 id="workflow-title">{t('advanced.technicalWorkflow')}</h2>
        <WorkflowDiagram />
        {workflows().map((item) => (
          <details className="panel workflow-detail" key={item.title}>
            <summary>{item.title}</summary>
            <p>{item.body}</p>
            <p>{item.detail}</p>
          </details>
        ))}
      </section>
    </section>
  )
}
