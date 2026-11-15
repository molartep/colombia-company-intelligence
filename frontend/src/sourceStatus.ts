import type { MarketSource } from './types/capitalMarkets'

export function sourceNeedsAttention(source: MarketSource) {
  return Boolean(
    source.last_error ||
    source.last_ingestion_status === 'failed' ||
    source.availability === 'failed_to_retrieve' ||
    (source.stale && source.latest_snapshot),
  )
}

export function sourceErrorDescription(error: string | null | undefined) {
  const descriptions: Record<string, string> = {
    capital_source_timeout: 'Se agotó el tiempo de espera al consultar SFC.',
    capital_source_unavailable: 'El reporte SFC no estuvo disponible tras los intentos permitidos.',
    capital_source_rejected: 'SFC rechazó la descarga pública del reporte.',
    rnve_summary_unavailable: 'No se pudo cargar el resumen público del emisor.',
  }
  return error ? descriptions[error] : undefined
}
