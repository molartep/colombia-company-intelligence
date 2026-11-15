import type { MarketSource } from '../types/capitalMarkets'
import { sourceErrorDescription } from '../sourceStatus'
import { dateTime } from '../utils'

export function SourceEvidenceStatus({ source }: { source: MarketSource }) {
  const failed =
    source.last_ingestion_status === 'failed' ||
    source.availability === 'failed_to_retrieve' ||
    Boolean(source.last_error)
  return (
    <div className="source-evidence-status">
      <strong>{source.name}</strong>
      <p>
        {failed
          ? 'La última actualización falló. Se conserva la evidencia anterior cuando está disponible.'
          : 'Los datos de esta fuente superan el plazo de vigencia configurado.'}
      </p>
      <dl>
        <div>
          <dt>Última recuperación exitosa</dt>
          <dd>{dateTime(source.last_success_at)}</dd>
        </div>
        <div>
          <dt>Fecha de los datos en la fuente</dt>
          <dd>
            {dateTime(
              source.latest_snapshot?.observed_at ?? source.latest_snapshot?.published_at ?? null,
            )}
          </dd>
        </div>
        <div>
          <dt>Último intento</dt>
          <dd>{dateTime(source.last_attempt_at)}</dd>
        </div>
      </dl>
      {failed && (
        <p className="source-error">
          Último error: {sourceErrorDescription(source.last_error)}{' '}
          <code>{source.last_error || 'La fuente no registró detalles del error.'}</code>
        </p>
      )}
    </div>
  )
}
