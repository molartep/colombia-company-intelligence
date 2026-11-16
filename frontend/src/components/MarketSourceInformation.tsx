import type { MarketsProfile } from '../types/capitalMarkets'
import { dateTime } from '../utils'
import { sourceNeedsAttention, sourceErrorDescription } from '../sourceStatus'
import { RefreshAlert } from './Feedback'
import { SourceInformationCard } from './SourceInformationCard'

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
  return (
    <SourceInformationCard title="Data Source Information" id="capital-market-sources">
      <p className="muted source-introduction">
        Fuentes oficiales consultadas, fechas de verificación y alcance de la evidencia.
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
              ? 'Fuente temporalmente no disponible'
              : source.availability === 'not_yet_checked'
                ? 'Fuente aún no consultada'
                : source.availability === 'requires_authorized_source'
                  ? 'Requiere una fuente autorizada'
                  : source.stale
                    ? 'Evidencia desactualizada'
                    : 'Disponible'
          return (
            <section
              className="source-provider"
              key={source.id}
              aria-label={source.name}
              id={`capital-source-${source.id}`}
              tabIndex={-1}
            >
              <div className="source-provider-heading">
                <h3>{source.name}</h3>
                <span
                  className={`badge ${problem ? 'value-pill--review' : source.availability === 'available' ? 'value-pill--present' : 'value-pill--muted'}`}
                >
                  {status}
                </span>
              </div>
              <p className="small muted">{source.institution}</p>
              <a className="text-link" href={source.source_url} target="_blank" rel="noreferrer">
                Fuente oficial ↗
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
                  aria-label={`Refresh ${source.name}`}
                >
                  {refreshing && activeSource === source.id ? 'Refreshing…' : 'Refresh data'}
                </button>
              )}
              {!refreshable && (
                <button
                  type="button"
                  className="refresh-button source-refresh"
                  disabled
                  aria-label={`Refresh ${source.name}`}
                >
                  Refresh data
                </button>
              )}
              {source.last_error && (
                <p className="source-error small" role="status">
                  Último error: {sourceErrorDescription(source.last_error)}{' '}
                  <code>{source.last_error}</code>
                </p>
              )}
              {activeSource === source.id && refreshError && (
                <RefreshAlert refresh={() => refresh(source.id)} refreshing={refreshing}>
                  {refreshError.message} Los datos anteriores se conservan.
                </RefreshAlert>
              )}
              {activeSource === source.id && refreshed && (
                <p className="small muted" role="status">
                  {source.last_ingestion_status === 'failed'
                    ? 'No se pudo actualizar esta fuente. Se conserva la evidencia anterior.'
                    : 'Se completó la consulta de esta fuente.'}
                </p>
              )}
              {source.id === 'sfc_rnve' && (
                <p className="small muted source-scope-note">
                  El directorio requiere importar una nueva exportación oficial; no admite
                  actualización desde este perfil.
                </p>
              )}
              <section
                className="source-freshness source-freshness--four"
                aria-label={`Fechas de ${source.name}`}
              >
                <h3>Fechas de verificación</h3>
                <dl>
                  <div>
                    <dt>Último intento</dt>
                    <dd>{dateTime(source.last_attempt_at)}</dd>
                  </div>
                  <div>
                    <dt>Última ingesta exitosa</dt>
                    <dd>{dateTime(source.last_success_at)}</dd>
                  </div>
                  <div>
                    <dt>Fecha publicada</dt>
                    <dd>{dateTime(source.latest_snapshot?.published_at ?? null)}</dd>
                  </div>
                  <div>
                    <dt>Observación / generación del reporte</dt>
                    <dd>{dateTime(source.latest_snapshot?.observed_at ?? null)}</dd>
                  </div>
                </dl>
              </section>
              {source.latest_snapshot && (
                <details className="source-disclosure">
                  <summary>Detalles de la evidencia</summary>
                  {source.id === 'sfc_rnve' && (
                    <p className="small muted">
                      {source.latest_snapshot.complete_current
                        ? 'Cobertura: directorio vigente completo confirmado al importar.'
                        : 'Cobertura: parcial o no certificada; no permite conclusiones negativas.'}
                    </p>
                  )}
                  <dl>
                    <div>
                      <dt>Snapshot</dt>
                      <dd className="hash">{source.latest_snapshot.id}</dd>
                    </div>
                    <div>
                      <dt>Payload SHA-256</dt>
                      <dd className="hash">
                        {source.latest_snapshot.content_hash ?? 'No informado'}
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
        <summary>Alcance y limitaciones</summary>
        <ul className="market-limitations">
          {data.limitations.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </details>
    </SourceInformationCard>
  )
}
