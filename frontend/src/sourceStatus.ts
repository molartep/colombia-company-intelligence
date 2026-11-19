import { t } from './i18n'
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
    quote_identity_missing: t('sourceErrors.laPaginaContieneUnPrecioPeroNoAportaNitAnn'),
    sfc_quote_unavailable: t('sourceErrors.noSePudoRecuperarElReportePublicoDeCotizacionSfc'),
    lr_directory_unavailable: t('sourceErrors.noSePudoConsultarElDirectorioDeAccionesDelProveedor'),
    lr_no_candidate: t('sourceErrors.elDirectorioDelProveedorNoContieneUnaPaginaCandidataPara'),
    lr_ambiguous_match: t('sourceErrors.variasPaginasCoincidenConElEmisorNoSeSeleccionoUna'),
    lr_page_invalid: t('sourceErrors.laPaginaDescubiertaNoContieneUnaFichaValida'),
    quote_no_exact_match: t('sourceErrors.noSeEstablecioUnaCoincidenciaExactaPorNitAnnO'),
    lr_page_unavailable: t('sourceErrors.noSePudoRecuperarLaCotizacionPublicaDeLaRepublica'),
    bvc_http_403: t('sourceErrors.bvcBloqueoElAccesoASuPaginaPublicaHttp403'),
    bvc_transport_error: t('sourceErrors.noSePudoConectarConLaPaginaPublicaBvc'),
    capital_source_timeout: t('sourceErrors.seAgotoElTiempoDeEsperaAlConsultarSfc'),
    capital_source_unavailable: t(
      'sourceErrors.elReporteSfcNoEstuvoDisponibleTrasLosIntentosPermitidos',
    ),
    capital_source_rejected: t('sourceErrors.sfcRechazoLaDescargaPublicaDelReporte'),
    rnve_summary_unavailable: t('sourceErrors.noSePudoCargarElResumenPublicoDelEmisor'),
  }
  return error ? descriptions[error] : undefined
}
