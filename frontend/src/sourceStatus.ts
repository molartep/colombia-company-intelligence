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
    quote_identity_missing:
      'La página contiene un precio, pero no aporta NIT, ANN ni razón social verificables.',
    sfc_quote_unavailable: 'No se pudo recuperar el reporte público de cotización SFC.',
    lr_directory_unavailable: 'No se pudo consultar el directorio de acciones del proveedor.',
    lr_no_candidate:
      'El directorio del proveedor no contiene una página candidata para este emisor.',
    lr_ambiguous_match: 'Varias páginas coinciden con el emisor; no se seleccionó una cotización.',
    lr_page_invalid: 'La página descubierta no contiene una ficha válida.',
    quote_no_exact_match: 'No se estableció una coincidencia exacta por NIT, ANN o razón social.',
    lr_page_unavailable: 'No se pudo recuperar la cotización pública de La República.',
    bvc_http_403: 'BVC bloqueó el acceso a su página pública (HTTP 403).',
    bvc_transport_error: 'No se pudo conectar con la página pública BVC.',
    capital_source_timeout: 'Se agotó el tiempo de espera al consultar SFC.',
    capital_source_unavailable: 'El reporte SFC no estuvo disponible tras los intentos permitidos.',
    capital_source_rejected: 'SFC rechazó la descarga pública del reporte.',
    rnve_summary_unavailable: 'No se pudo cargar el resumen público del emisor.',
  }
  return error ? descriptions[error] : undefined
}
