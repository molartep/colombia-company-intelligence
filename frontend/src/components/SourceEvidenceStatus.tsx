import { uiMessage } from '../i18n/messages'
import { t, useLanguage } from '../i18n'
import type { MarketSource } from '../types/capitalMarkets'
import { sourceErrorDescription } from '../sourceStatus'
import { dateTime } from '../utils'

export function SourceEvidenceStatus({ source }: { source: MarketSource }) {
  useLanguage()

  const failed =
    source.last_ingestion_status === 'failed' ||
    source.availability === 'failed_to_retrieve' ||
    Boolean(source.last_error)
  return (
    <div className="source-evidence-status">
      <strong>{uiMessage(source.name)}</strong>
      <p>
        {failed
          ? t('sourceEvidence.laUltimaActualizacionFalloSeConservaLaEvidenciaAnteriorCuando')
          : t('sourceEvidence.losDatosDeEstaFuenteSuperanElPlazoDeVigencia')}
      </p>
      <dl>
        <div>
          <dt>{t('sourceEvidence.ultimaRecuperacionExitosa')}</dt>
          <dd>{dateTime(source.last_success_at)}</dd>
        </div>
        <div>
          <dt>{t('sourceEvidence.fechaDeLosDatosEnLaFuente')}</dt>
          <dd>
            {dateTime(
              source.latest_snapshot?.observed_at ?? source.latest_snapshot?.published_at ?? null,
            )}
          </dd>
        </div>
        <div>
          <dt>{t('sourceEvidence.ultimoIntento')}</dt>
          <dd>{dateTime(source.last_attempt_at)}</dd>
        </div>
      </dl>
      {failed && (
        <p className="source-error">
          {' '}
          {t('sourceEvidence.ultimoError')} {sourceErrorDescription(source.last_error)}{' '}
          <code>{source.last_error || t('sourceEvidence.laFuenteNoRegistroDetallesDelError')}</code>
        </p>
      )}
    </div>
  )
}
