import { uiMessage, errorMessage } from '../i18n/messages'
import { t, useLanguage } from '../i18n'
import type { MarketsProfile } from '../types/capitalMarkets'
import { dateTime } from '../utils'
import { sourceNeedsAttention, sourceErrorDescription } from '../sourceStatus'
import { RefreshAlert } from './Feedback'
import { SourceInformationCard } from './SourceInformationCard'
import { DirectoryImport } from './DirectoryImport'

export function MarketSourceInformation({
  data,
  refresh,
  refreshing,
  activeSource,
  refreshError,
  refreshed,
}: {
  data: MarketsProfile
  refresh: (source: string) => void
  refreshing: boolean
  activeSource?: string
  refreshError?: Error | null
  refreshed?: boolean
}) {
  useLanguage()

  return (
    <SourceInformationCard
      title={t('marketSources.dataSourceInformation')}
      id="capital-market-sources"
    >
      <p className="muted source-introduction">
        {' '}
        {t('marketSources.fuentesOficialesConsultadasFechasDeVerificacionYAlcanceDeLa')}
      </p>
      <div className="source-providers">
        {data.sources.map((source) => {
          const refreshable = [
            'sfc_rnve_securities',
            'sfc_rnve_issuer_details',
            'bvc_listings',
            'la_republica_quotes',
            'sfc_daily_quotes',
          ].includes(source.id)
          const problem = sourceNeedsAttention(source)
          const status =
            source.availability === 'failed_to_retrieve'
              ? t('marketSources.fuenteTemporalmenteNoDisponible')
              : source.availability === 'not_yet_checked'
                ? t('marketSources.fuenteAunNoConsultada')
                : source.availability === 'requires_authorized_source'
                  ? t('marketSources.requiereUnaFuenteAutorizada')
                  : source.stale
                    ? t('marketSources.evidenciaDesactualizada')
                    : t('marketSources.disponible')
          return (
            <section
              className="source-provider"
              key={source.id}
              aria-label={uiMessage(source.name)}
              id={`capital-source-${source.id}`}
              tabIndex={-1}
            >
              <div className="source-provider-heading">
                <h3>{uiMessage(source.name)}</h3>
                <span
                  className={`badge ${problem ? 'value-pill--review' : source.availability === 'available' ? 'value-pill--present' : 'value-pill--muted'}`}
                >
                  {status}
                </span>
              </div>
              <p className="small muted">{source.institution}</p>
              <a className="text-link" href={source.source_url} target="_blank" rel="noreferrer">
                {' '}
                {t('marketSources.fuenteOficial')}
              </a>
              {refreshable && data.rnve.match_status === 'verified' && (
                <button
                  type="button"
                  className="refresh-button source-refresh"
                  disabled={
                    refreshing ||
                    ((data.common_equity_record_count ?? 0) > 1 &&
                      ['bvc_listings', 'la_republica_quotes', 'sfc_daily_quotes'].includes(
                        source.id,
                      ))
                  }
                  aria-busy={refreshing && activeSource === source.id}
                  onClick={() => refresh(source.id)}
                  aria-label={t('marketSources.refreshValue', { value0: uiMessage(source.name) })}
                >
                  {refreshing && activeSource === source.id
                    ? t('marketSources.refreshing')
                    : t('marketSources.refreshData')}
                </button>
              )}
              {!refreshable && source.id !== 'sfc_rnve' && (
                <button
                  type="button"
                  className="refresh-button source-refresh"
                  disabled
                  aria-label={t('marketSources.refreshValue', { value0: uiMessage(source.name) })}
                >
                  {' '}
                  {t('marketSources.refreshData')}
                </button>
              )}
              {source.last_error && (
                <p className="source-error small" role="status">
                  {' '}
                  {t('marketSources.ultimoError')} {sourceErrorDescription(source.last_error)}{' '}
                  <code>{source.last_error}</code>
                </p>
              )}
              {activeSource === source.id && refreshError && (
                <RefreshAlert refresh={() => refresh(source.id)} refreshing={refreshing}>
                  {errorMessage(refreshError)} {t('marketSources.losDatosAnterioresSeConservan')}
                </RefreshAlert>
              )}
              {activeSource === source.id && refreshed && (
                <p className="small muted" role="status">
                  {source.last_ingestion_status === 'failed'
                    ? t('marketSources.noSePudoActualizarEstaFuenteSeConservaLaEvidencia')
                    : t('marketSources.seCompletoLaConsultaDeEstaFuente')}
                </p>
              )}
              {source.id === 'sfc_rnve' && <DirectoryImport />}
              <section
                className="source-freshness source-freshness--four"
                aria-label={t('marketSources.fechasDeValue', { value0: uiMessage(source.name) })}
              >
                <h3>{t('marketSources.fechasDeVerificacion')}</h3>
                <dl>
                  <div>
                    <dt>{t('marketSources.ultimoIntento')}</dt>
                    <dd>{dateTime(source.last_attempt_at)}</dd>
                  </div>
                  <div>
                    <dt>{t('marketSources.ultimaIngestaExitosa')}</dt>
                    <dd>{dateTime(source.last_success_at)}</dd>
                  </div>
                  <div>
                    <dt>{t('marketSources.fechaPublicada')}</dt>
                    <dd>{dateTime(source.latest_snapshot?.published_at ?? null)}</dd>
                  </div>
                  <div>
                    <dt>{t('marketSources.observacionGeneracionDelReporte')}</dt>
                    <dd>{dateTime(source.latest_snapshot?.observed_at ?? null)}</dd>
                  </div>
                </dl>
              </section>
              {source.latest_snapshot && (
                <details className="source-disclosure">
                  <summary>{t('marketSources.detallesDeLaEvidencia')}</summary>
                  {source.id === 'sfc_rnve' && (
                    <p className="small muted">
                      {source.latest_snapshot.complete_current
                        ? t('marketSources.coberturaDirectorioVigenteCompletoConfirmadoAlImportar')
                        : t(
                            'marketSources.coberturaParcialONoCertificadaNoPermiteConclusionesNegativas',
                          )}
                    </p>
                  )}
                  <dl>
                    <div>
                      <dt>{t('marketSources.snapshot')}</dt>
                      <dd className="hash">{source.latest_snapshot.id}</dd>
                    </div>
                    <div>
                      <dt>{t('marketSources.payloadSha256')}</dt>
                      <dd className="hash">
                        {source.latest_snapshot.content_hash ?? t('marketSources.noInformado')}
                      </dd>
                    </div>
                  </dl>
                </details>
              )}
            </section>
          )
        })}
      </div>
      <details className="source-disclosure">
        <summary>{t('marketSources.alcanceYLimitaciones')}</summary>
        <ul className="market-limitations">
          {data.limitations.map((note) => (
            <li key={note}>{uiMessage(note)}</li>
          ))}
        </ul>
      </details>
    </SourceInformationCard>
  )
}
