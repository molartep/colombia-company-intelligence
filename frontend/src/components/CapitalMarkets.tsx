import { formatNumber } from '../i18n/format'
import { FitMetricValue } from './FitMetricValue'
import { uiMessage, errorMessage } from '../i18n/messages'
import { formatCurrency, formatDecimal } from '../i18n/format'
import { t, useLanguage } from '../i18n'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import {
  categories,
  type ListingStatus,
  type MarketIssuer,
  type RegistrationStatus,
} from '../types/capitalMarkets'
import { Failure, Loading, RefreshAlert } from './Feedback'
import { SourceEvidenceStatus } from './SourceEvidenceStatus'
import { sourceNeedsAttention, sourceErrorDescription } from '../sourceStatus'
import { SourceInformationCard } from './SourceInformationCard'
import { MarketSourceInformation } from './MarketSourceInformation'
import { MissingValue } from './FieldValues'
import { DirectoryImport } from './DirectoryImport'
import { FilterHelp } from './AdvancedFilters'
import { dateTime, registrationDate, issuanceMonth } from '../utils'

const registrationLabels = (): Record<RegistrationStatus, string> => ({
  registered_active: t('capitalMarkets.inscritoEnRnve'),
  registered_cancelled: t('capitalMarkets.inscripcionCancelada'),
  historical: t('capitalMarkets.registroHistorico'),
  not_found_in_checked_source: t('capitalMarkets.sinCoincidenciaEnLaFuenteConsultada'),
  unknown: t('capitalMarkets.registroNoDeterminado'),
})
const listingLabels = (): Record<ListingStatus, string> => ({
  verified_listed: t('capitalMarkets.listadoVerificado'),
  verified_delisted: t('capitalMarkets.deslistadoVerificado'),
  not_found_in_checked_source: t('capitalMarkets.sinCoincidenciaEnLaFuenteConsultada'),
  unknown: t('capitalMarkets.listadoNoVerificado'),
})
const availability = (): Record<string, string> => ({
  not_yet_checked: t('capitalMarkets.valoresAunNoConsultadosParaEsteEmisorNoSeHa'),
  failed_to_retrieve: t(
    'capitalMarkets.fuenteTemporalmenteNoDisponibleLaConsultaFalloNoSignificaAusencia',
  ),
  stale: t('capitalMarkets.seMuestranInstrumentosDeUnaObservacionAnteriorSuVigenciaRequiere'),
  available: '',
})
const date = (value: string | null) =>
  value ? (registrationDate(value)?.display ?? value) : t('capitalMarkets.noInformado')

function PublicLink({ value }: { value: string | null | undefined }) {
  useLanguage()

  if (!value) return <MissingValue />
  let href: string | undefined
  try {
    const url = new URL(/^www\./i.test(value) ? `https://${value}` : value)
    if (
      ['https:', 'http:'].includes(url.protocol) &&
      url.hostname.includes('.') &&
      !url.username &&
      !url.password
    )
      href = url.href
  } catch {
    /* Preserve source text when it is not a valid public link. */
  }
  if (href)
    return (
      <a className="text-link" href={href} target="_blank" rel="noreferrer">
        {value} ↗
      </a>
    )
  return <>{value}</>
}

function AdministrationValue({
  value,
  issuer,
}: {
  value?: string | number | null
  issuer?: MarketIssuer
}) {
  useLanguage()

  if (value !== null && value !== undefined && value !== '')
    return <>{typeof value === 'number' ? formatNumber(value) : value}</>
  if (issuer?.details_availability === 'available' || issuer?.details_availability === 'stale')
    return <MissingValue />
  return (
    <span
      className={`badge ${issuer?.details_availability === 'failed_to_retrieve' ? 'value-pill--missing' : 'value-pill--muted'}`}
    >
      {issuer?.details_availability === 'failed_to_retrieve'
        ? t('capitalMarkets.unavailable')
        : t('capitalMarkets.notYetChecked')}
    </span>
  )
}

export function CapitalMarkets({ companyId }: { companyId: string }) {
  useLanguage()

  const client = useQueryClient()
  const refresh = useMutation({
    mutationFn: (source: string) => api.capitalMarkets(companyId, undefined, true, source),
    onSuccess: (data) => {
      client.setQueryData(['capital-markets', companyId], data)
      setPage(1)
    },
  })
  const goToSources = (source?: string) => {
    const card = document.getElementById('capital-market-sources')
    if (card instanceof HTMLDetailsElement) card.open = true
    const target = (source && document.getElementById(`capital-source-${source}`)) || card
    target?.scrollIntoView?.({
      behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
        ? 'auto'
        : 'smooth',
      block: 'start',
    })
    target?.focus({ preventScroll: true })
  }
  const refreshData = () => goToSources()
  const [page, setPage] = useState(1)
  const [category, setCategory] = useState('')
  const [exchange, setExchange] = useState('')
  const [listingStatus, setListingStatus] = useState('')
  const markets = useQuery({
    queryKey: ['capital-markets', companyId],
    refetchOnMount: 'always',
    refetchOnWindowFocus: false,
    queryFn: ({ signal }) => api.capitalMarkets(companyId, signal),
    staleTime: 5 * 60_000,
  })
  const securities = useQuery({
    queryKey: [
      'securities',
      companyId,
      markets.dataUpdatedAt,
      page,
      category,
      exchange,
      listingStatus,
    ],
    queryFn: ({ signal }) =>
      api.securities(companyId, page, category, exchange, listingStatus, signal),
    enabled:
      markets.isSuccess &&
      !markets.isFetching &&
      !refresh.isPending &&
      markets.data.rnve.match_status === 'verified',
    staleTime: 5 * 60_000,
  })
  if (markets.isPending) return <Loading />
  if (markets.isError) return <Failure error={markets.error} retry={() => void markets.refetch()} />
  const data = markets.data
  const verified = data.rnve.match_status === 'verified'
  const issuer = verified
    ? data.issuers.find((item) => item.match_status === 'verified')
    : undefined
  const instruments = securities.data?.items ?? []
  const sourceAlerts = data.sources.filter(sourceNeedsAttention)
  const alerts = sourceAlerts.map((source) => (
    <RefreshAlert key={source.id} refresh={() => goToSources(source.id)}>
      <SourceEvidenceStatus source={source} />
    </RefreshAlert>
  ))
  if (data.sources.some((source) => source.id === 'sfc_rnve' && !source.latest_snapshot))
    alerts.unshift(
      <div className="notice warning" role="alert" key="directory-missing">
        <strong>
          {' '}
          {t('capitalMarkets.importTheRnveIssuerDirectoryToEnableCapitalMarketsIdentity')}
        </strong>
        <DirectoryImport />
      </div>,
    )
  if ((data.common_equity_record_count ?? 0) > 1)
    alerts.push(
      <div className="notice danger" role="alert" key="multiple-common-equity">
        {' '}
        {t('capitalMarkets.seEncontraron')} {data.common_equity_record_count}{' '}
        {t('capitalMarkets.registrosDeAccionesOrdinariasEnValoresRegistradosLaConsultaDe')}
      </div>,
    )
  if (refresh.isError)
    alerts.push(
      <RefreshAlert key="refresh-error" refresh={refreshData}>
        <strong>
          {uiMessage(
            data.sources.find((source) => source.id === refresh.variables)?.name ??
              refresh.variables,
          )}
        </strong>
        <p>
          {errorMessage(refresh.error)} {t('capitalMarkets.losDatosAnterioresSeConservan')}
        </p>
      </RefreshAlert>,
    )
  if (data.rnve.match_status === 'potential')
    alerts.push(
      <RefreshAlert key="identity" refresh={refreshData}>
        {' '}
        {t('capitalMarkets.posibleCoincidenciaDeIdentidadPendienteDeRevisionLosInstrumentosDel')}
      </RefreshAlert>,
    )
  if (
    issuer &&
    ['stale', 'failed_to_retrieve'].includes(issuer.details_availability ?? '') &&
    !sourceAlerts.some((s) => s.id === 'sfc_rnve_issuer_details')
  )
    alerts.push(
      <RefreshAlert key="summary-details" refresh={refreshData}>
        <strong>{t('capitalMarkets.sfcDatosDelEmisorRnve')}</strong>
        <p>
          {issuer.details_availability === 'failed_to_retrieve'
            ? t('capitalMarkets.noSePudoRecuperarElResumenRnveNoSignificaQue')
            : t('capitalMarkets.seConservanLosUltimosDatosRecuperadosDelRnve')}
        </p>
        <p>
          {' '}
          {t('capitalMarkets.ultimaRecuperacion')}{' '}
          {dateTime(issuer.administration_retrieved_at ?? null)} {t('capitalMarkets.ultimoIntento')}{' '}
          {dateTime(issuer.details_last_attempt_at ?? null)}
        </p>
      </RefreshAlert>,
    )
  if (
    verified &&
    securities.data &&
    ['stale', 'failed_to_retrieve', 'not_yet_checked'].includes(securities.data.availability) &&
    !sourceAlerts.some((s) => s.id === 'sfc_rnve_securities')
  )
    alerts.push(
      <RefreshAlert key="securities-status" refresh={refreshData}>
        <strong>{t('capitalMarkets.sfcValoresRegistrados')}</strong>
        <p>{availability()[securities.data.availability]}</p>
      </RefreshAlert>,
    )
  return (
    <section className="capital-markets" aria-label={t('capitalMarkets.capitalMarkets')}>
      <h2>{t('capitalMarkets.capitalMarkets')}</h2>
      {markets.isFetching && <Loading />}
      {refresh.isPending && <Loading />}
      {alerts.length > 0 && (
        <details className="panel market-alerts">
          <summary>
            {' '}
            {t('capitalMarkets.alertas')}
            {formatNumber(alerts.length)})
          </summary>
          {alerts}
        </details>
      )}
      <div className="profile-grid">
        <article className="panel">
          <h3>{t('capitalMarkets.registroNacionalDeValoresYEmisores')}</h3>
          <span
            className={`badge ${data.rnve.status === 'registered_active' ? 'value-pill--present' : data.rnve.status === 'registered_cancelled' ? 'value-pill--missing' : 'value-pill--muted'}`}
          >
            {registrationLabels()[data.rnve.status]}
          </span>
          {data.issuers.map((issuer) => (
            <div className="market-issuer" key={issuer.id}>
              <h4>{issuer.issuer_name}</h4>
              <dl>
                <div>
                  <dt>{t('capitalMarkets.nitNormalizado')}</dt>
                  <dd>
                    {issuer.nit ?? t('capitalMarkets.noInformado')}
                    {issuer.verification_digit ? `-${issuer.verification_digit}` : ''}
                  </dd>
                </div>
                <div>
                  <dt>{t('capitalMarkets.identificadorOriginalSfc')}</dt>
                  <dd>{issuer.source_nit ?? t('capitalMarkets.noInformado')}</dd>
                </div>
                <div>
                  <dt>{t('capitalMarkets.tipoDeEntidad')}</dt>
                  <dd>
                    {issuer.regulator_entity_type ?? <MissingValue />} —{' '}
                    {issuer.regulator_entity_type_description ?? <MissingValue />}
                  </dd>
                </div>
                <div>
                  <dt>{t('capitalMarkets.codigoDeEntidad')}</dt>
                  <dd>{issuer.regulator_entity_code ?? <MissingValue />}</dd>
                </div>
                <div>
                  <dt>{t('capitalMarkets.verificado')}</dt>
                  <dd>{dateTime(issuer.last_verified_at)}</dd>
                </div>
                <div>
                  <dt>{t('capitalMarkets.identidad')}</dt>
                  <dd>
                    {issuer.match_status === 'verified'
                      ? t('capitalMarkets.nitVerificado')
                      : t('capitalMarkets.coincidenciaPotencial')}
                  </dd>
                </div>
              </dl>
              <a className="text-link" href={issuer.source_url} target="_blank" rel="noreferrer">
                {' '}
                {t('capitalMarkets.fuenteOficialRnve')}
              </a>
            </div>
          ))}
        </article>
        <article className="panel">
          <h3>{t('capitalMarkets.bolsaDeValoresDeColombia')}</h3>
          {data.has_registered_bvc_common_equity ? (
            <div className="bvc-registration">
              <span className="badge value-pill--present">{t('capitalMarkets.registrado')}</span>
              <FilterHelp
                label={t('capitalMarkets.registroBvc')}
                text={t('capitalMarkets.existeAlMenosUnRegistroEnValoresRegistradosConCategoria')}
              />
            </div>
          ) : (
            <span
              className={`badge ${data.exchange_listing.status === 'verified_listed' ? 'value-pill--present' : 'value-pill--muted'}`}
            >
              {listingLabels()[data.exchange_listing.status]}
            </span>
          )}
          {!data.exchange_listing.quotes?.length && (data.common_equity_record_count ?? 0) <= 1 && (
            <div className="notice danger" role="alert">
              {' '}
              {t('capitalMarkets.noSeHaEstablecidoUnaCoincidenciaExactaPorNitAnn')}
            </div>
          )}
          {(data.exchange_listing.quotes?.length ?? 0) > 0 ? (
            data.exchange_listing.quotes!.map((quote) => (
              <div className="bvc-quote" key={`${quote.source_id ?? 'bvc'}-${quote.instrument_id}`}>
                <div className="quote-heading">
                  <h4>
                    <span className="quote-ticker-label">
                      {quote.ticker
                        ? t('capitalMarkets.nemotecnicoTicker')
                        : t('capitalMarkets.emisor')}
                    </span>
                    {quote.ticker ?? quote.reported_legal_name ?? <MissingValue />}
                  </h4>
                  {quote.stale && (
                    <span className="badge value-pill--review">
                      {' '}
                      {t('capitalMarkets.actualizacionPendiente')}
                    </span>
                  )}
                </div>
                <div className="quote-highlight">
                  <div>
                    <span className="quote-label">
                      {quote.price_kind === 'daily_weighted_average'
                        ? t('capitalMarkets.precioPromedioPonderadoDiario')
                        : t('capitalMarkets.ultimoPrecio')}
                    </span>
                    <p className="bvc-price">
                      {quote.last_price !== null ? (
                        <FitMetricValue
                          value={
                            quote.currency
                              ? formatCurrency(quote.last_price, quote.currency)
                              : formatDecimal(quote.last_price)
                          }
                        />
                      ) : (
                        <MissingValue />
                      )}
                    </p>
                  </div>
                  {quote.variation_percent != null && (
                    <div
                      className={`quote-change ${Number(quote.variation_percent) > 0 ? 'quote-up' : Number(quote.variation_percent) < 0 ? 'quote-down' : ''}`}
                    >
                      <span className="quote-label">{t('capitalMarkets.variacion')}</span>
                      <strong>
                        {Number(quote.variation_percent) > 0
                          ? '↑ +'
                          : Number(quote.variation_percent) < 0
                            ? '↓ '
                            : ''}
                        {formatDecimal(quote.variation_percent)}%
                      </strong>
                    </div>
                  )}
                </div>
                <p className="quote-date">
                  <span>{t('capitalMarkets.fechaDelPrecio')}</span>
                  {quote.price_date
                    ? registrationDate(quote.price_date.replaceAll('-', ''))?.display
                    : quote.price_as_of
                      ? dateTime(quote.price_as_of)
                      : t('capitalMarkets.noInformada')}
                </p>
                <dl className="quote-metrics">
                  {quote.volume != null && (
                    <div>
                      <dt>{t('capitalMarkets.volumen')}</dt>
                      <dd>{formatDecimal(quote.volume)}</dd>
                    </div>
                  )}
                  <div>
                    <dt>
                      {quote.source_id === 'la_republica_quotes'
                        ? t('capitalMarkets.annDelRegistroRnve')
                        : t('capitalMarkets.codigoSuperfinanciera')}
                    </dt>
                    <dd>{quote.superfinanciera_code}</dd>
                  </div>
                  {quote.isin && (
                    <div>
                      <dt>ISIN</dt>
                      <dd>{quote.isin}</dd>
                    </div>
                  )}
                </dl>
                <div className="quote-provenance">
                  <a className="text-link" href={quote.source_url} target="_blank" rel="noreferrer">
                    {' '}
                    {t('capitalMarkets.fuente')}{' '}
                    {quote.source_name ?? 'Bolsa de Valores de Colombia'} ↗
                  </a>
                  <p>
                    {' '}
                    {t('capitalMarkets.coincidencia')}{' '}
                    {quote.match_type === 'exact_nit'
                      ? t('capitalMarkets.nitExacto')
                      : quote.match_type === 'exact_legal_name'
                        ? t('capitalMarkets.razonSocialExacta')
                        : t('capitalMarkets.annExacto')}{' '}
                    · {quote.matched_value ?? quote.superfinanciera_code}
                  </p>
                  <p>
                    {' '}
                    {t('capitalMarkets.recuperado')} {dateTime(quote.retrieved_at)}
                  </p>
                  {quote.source_note && (
                    <p className="quote-source-note">{uiMessage(quote.source_note)}</p>
                  )}
                </div>
              </div>
            ))
          ) : (
            <dl>
              <div>
                <dt>{t('capitalMarkets.ultimoPrecio')}</dt>
                <dd>
                  <span className="badge value-pill--muted">
                    {' '}
                    {t('capitalMarkets.noVerificado')}
                  </span>
                </dd>
              </div>
              <div>
                <dt>{t('capitalMarkets.nemotecnicoTicker')}</dt>
                <dd>
                  <span className="badge value-pill--muted">
                    {' '}
                    {t('capitalMarkets.noVerificado')}
                  </span>
                </dd>
              </div>
            </dl>
          )}
          {(data.exchange_listing.attempts?.length ?? 0) > 0 && (
            <details className="quote-attempts" open={!data.exchange_listing.quotes?.length}>
              <summary>
                {' '}
                {t('capitalMarkets.fuentesDeCotizacion')}
                {formatNumber(data.exchange_listing.attempts!.length)})
              </summary>
              <ul>
                {data.exchange_listing.attempts!.map((attempt) => (
                  <li key={attempt.source_id}>
                    <div>
                      {attempt.source_url ? (
                        <a href={attempt.source_url} target="_blank" rel="noreferrer">
                          {attempt.source_name} ↗
                        </a>
                      ) : (
                        <span>{attempt.source_name}</span>
                      )}
                      <span
                        className={`badge ${attempt.status === 'matched' ? 'value-pill--present' : attempt.status === 'not_configured' || attempt.status === 'not_checked' ? 'value-pill--muted' : 'value-pill--review'}`}
                      >
                        {(
                          {
                            matched: t('capitalMarkets.coincidenciaExacta'),
                            no_exact_match: t('capitalMarkets.sinIdentidadVerificable'),
                            unavailable: t('capitalMarkets.noDisponible'),
                            not_configured: t('capitalMarkets.sinRutaVerificada'),
                            not_checked: t('capitalMarkets.noConsultada'),
                          } as Record<string, string>
                        )[attempt.status] ?? attempt.status}
                      </span>
                    </div>
                    {attempt.detail && (
                      <p>{sourceErrorDescription(attempt.detail) ?? attempt.detail}</p>
                    )}
                    {attempt.last_attempt_at && (
                      <p>
                        {' '}
                        {t('capitalMarkets.ultimoIntento2')} {dateTime(attempt.last_attempt_at)}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </article>
      </div>
      <div className="profile-grid">
        <article className="panel market-contact">
          <h3>{t('capitalMarkets.datosDeContacto')}</h3>
          <dl>
            {(
              [
                [t('capitalMarkets.correoInstitucional'), issuer?.contacts?.institutional_email],
                [t('capitalMarkets.direccion'), issuer?.contacts?.address],
                [t('capitalMarkets.ciudad'), issuer?.contacts?.city],
                [t('capitalMarkets.telefono'), issuer?.contacts?.phone],
              ] as const
            ).map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value || <MissingValue />}</dd>
              </div>
            ))}
            <div>
              <dt>{t('capitalMarkets.web')}</dt>
              <dd>
                <PublicLink value={issuer?.contacts?.website} />
              </dd>
            </div>
            <div>
              <dt>{t('capitalMarkets.redesSociales')}</dt>
              <dd>
                {issuer?.contacts?.social_networks?.length ? (
                  issuer.contacts.social_networks.map((value) => (
                    <p key={value}>
                      <PublicLink value={value} />
                    </p>
                  ))
                ) : (
                  <AdministrationValue issuer={issuer} />
                )}
              </dd>
            </div>
          </dl>
          {issuer?.contacts_source_url && (
            <p className="small muted">
              <a
                className="text-link"
                href={issuer.contacts_source_url}
                target="_blank"
                rel="noreferrer"
              >
                {' '}
                {t('capitalMarkets.fuenteRnve')}
              </a>{' '}
              {t('capitalMarkets.obtenido')} {dateTime(issuer.contacts_retrieved_at ?? null)}
            </p>
          )}
        </article>
        <article className="panel market-contact">
          <h3>{t('capitalMarkets.administracion')}</h3>
          <dl>
            <div>
              <dt>{t('capitalMarkets.nroMiembrosJuntaDirectiva')}</dt>
              <dd>
                <AdministrationValue
                  value={issuer?.administration?.board_members_count}
                  issuer={issuer}
                />
              </dd>
            </div>
            <div>
              <dt>{t('capitalMarkets.representanteLegalPrincipal')}</dt>
              <dd>
                <AdministrationValue
                  value={issuer?.administration?.legal_representative}
                  issuer={issuer}
                />
              </dd>
            </div>
            <div>
              <dt>
                {' '}
                {t(
                  'capitalMarkets.representanteLegalPrincipalResponsableDeLaInformacionPresentadaAlRnve',
                )}
              </dt>
              <dd>
                <AdministrationValue
                  value={issuer?.administration?.rnve_information_representative}
                  issuer={issuer}
                />
              </dd>
            </div>
          </dl>
          {issuer?.administration_source_url && (
            <p className="small muted">
              <a
                className="text-link"
                href={issuer.administration_source_url}
                target="_blank"
                rel="noreferrer"
              >
                {' '}
                {t('capitalMarkets.fuenteRnve')}
              </a>{' '}
              {t('capitalMarkets.obtenido')} {dateTime(issuer.administration_retrieved_at ?? null)}
            </p>
          )}
        </article>
      </div>
      <SourceInformationCard
        title={t('capitalMarkets.valoresRegistradosValue', {
          value0: securities.data ? ` (${securities.data.unfiltered_total})` : '',
        })}
        id="registered-securities"
      >
        {!verified ? (
          <p>
            {data.rnve.match_status === 'potential'
              ? t('capitalMarkets.verifiquePrimeroLaIdentidadDelEmisorCandidato')
              : t('capitalMarkets.noHayUnVinculoDeIdentidadVerificadoParaAtribuirInstrumentos')}
          </p>
        ) : (
          <>
            <div className="market-filters">
              <label>
                {' '}
                {t('capitalMarkets.categoria')}{' '}
                <select
                  value={category}
                  onChange={(event) => {
                    setCategory(event.target.value)
                    setPage(1)
                  }}
                >
                  <option value="">{t('capitalMarkets.todas')}</option>
                  {Object.entries(categories).map(([key, label]) => (
                    <option key={key} value={key}>
                      {' '}
                      {t(label)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {' '}
                {t('capitalMarkets.mercadoRegistrado')}{' '}
                <select
                  value={exchange}
                  onChange={(event) => {
                    setExchange(event.target.value)
                    setPage(1)
                  }}
                >
                  <option value="">{t('capitalMarkets.todos')}</option>
                  <option value="BVC">{t('capitalMarkets.bvcSegunSfc')}</option>
                </select>
              </label>
              <label>
                {' '}
                {t('capitalMarkets.estadoDeListado')}{' '}
                <select
                  value={listingStatus}
                  onChange={(event) => {
                    setListingStatus(event.target.value)
                    setPage(1)
                  }}
                >
                  <option value="">{t('capitalMarkets.todos')}</option>
                  {Object.entries(listingLabels()).map(([key, label]) => (
                    <option key={key} value={key}>
                      {' '}
                      {t(label)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {securities.isFetching && <Loading />}
            {securities.isError && (
              <Failure error={securities.error} retry={() => void securities.refetch()} />
            )}
            {securities.data && (
              <>
                <p className="securities-count small muted" role="status">
                  {formatNumber(securities.data.total)}{' '}
                  {securities.data.total === 1
                    ? t('capitalMarkets.recordFound')
                    : t('capitalMarkets.recordsFound')}
                </p>
                {instruments.length ? (
                  <div
                    className="table-wrap instruments-table-wrap"
                    role="region"
                    tabIndex={0}
                    aria-label={t('capitalMarkets.securitiesTable')}
                    aria-describedby="securities-scroll-hint"
                  >
                    <p className="table-scroll-hint" id="securities-scroll-hint">
                      {t('common.scrollTable')}
                    </p>
                    <table className="instruments-table">
                      <thead>
                        <tr>
                          <th>{t('capitalMarkets.instrumentoCategoria')}</th>
                          <th>{t('capitalMarkets.identificadores')}</th>
                          <th>{t('capitalMarkets.mercadoRegistrado')}</th>
                          <th>{t('capitalMarkets.fechasDeInscripcion')}</th>
                          <th>{t('capitalMarkets.estado')}</th>
                          <th className="numeric-cell">{t('capitalMarkets.importe')}</th>
                          <th>{t('capitalMarkets.calificacionReportada')}</th>
                          <th>{t('capitalMarkets.fuente2')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {instruments.map((instrument) => (
                          <tr key={instrument.id}>
                            <td>
                              <strong>{instrument.security_name}</strong>
                              <p>{t(categories[instrument.security_category])}</p>
                              <span className="muted small">
                                {' '}
                                {t('capitalMarkets.emision')}{' '}
                                {issuanceMonth(instrument.issuance_number)}
                              </span>
                            </td>
                            <td>
                              {instrument.ticker && (
                                <p>
                                  {' '}
                                  {t('capitalMarkets.ticker')} {instrument.ticker}
                                </p>
                              )}
                              {instrument.isin && <p>ISIN: {instrument.isin}</p>}
                              <p>ANN: {instrument.ann_code ?? t('capitalMarkets.noInformado')}</p>
                              {!instrument.ticker && (
                                <span className="muted small">
                                  {' '}
                                  {t('capitalMarkets.tickerNoInformado')}
                                </span>
                              )}
                            </td>
                            <td>
                              {instrument.exchange ?? t('capitalMarkets.rnveBolsaNoInformada')}
                            </td>
                            <td>
                              <p>RNVE: {date(instrument.rnve_registration_date)}</p>
                              <p>
                                {' '}
                                {t('capitalMarkets.bvc')} {date(instrument.bvc_registration_date)}
                              </p>
                            </td>
                            <td>
                              {listingLabels()[instrument.listing_status]}
                              {instrument.quality_notes?.map((note) => (
                                <p className="badge value-pill--review" key={note}>
                                  {uiMessage(note)}
                                </p>
                              ))}
                              {instrument.stale && (
                                <p className="badge value-pill--review">
                                  {' '}
                                  {t('capitalMarkets.observacionAnterior')}
                                </p>
                              )}
                            </td>
                            <td className="numeric-cell">
                              {instrument.authorized_amount === null
                                ? t('capitalMarkets.importeNoInformado')
                                : instrument.currency
                                  ? formatCurrency(
                                      instrument.authorized_amount,
                                      instrument.currency,
                                    )
                                  : formatDecimal(instrument.authorized_amount)}
                            </td>
                            <td>{instrument.credit_rating || t('capitalMarkets.noInformada')}</td>
                            <td>
                              <a
                                className="text-link"
                                href={instrument.source_url}
                                target="_blank"
                                rel="noreferrer"
                              >
                                {' '}
                                {t('capitalMarkets.sfc')}
                              </a>
                              <p className="small muted">
                                {' '}
                                {t('capitalMarkets.obtenido2')}{' '}
                                {dateTime(instrument.last_verified_at)}
                              </p>
                              <details>
                                <summary>{t('capitalMarkets.valoresOriginalesSfc')}</summary>
                                <dl>
                                  {Object.entries(instrument.source_values).map(
                                    ([field, value]) => (
                                      <div key={field}>
                                        <dt>{field}</dt>
                                        <dd>{value}</dd>
                                      </div>
                                    ),
                                  )}
                                </dl>
                              </details>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p>
                    {securities.data.availability === 'available'
                      ? t('capitalMarkets.noHayInstrumentosEnElReporteConsultadoQueSatisfaganEstos')
                      : t('capitalMarkets.noSePresentaUnaConclusionNegativaSobreInstrumentos')}
                  </p>
                )}
                <nav className="pagination" aria-label={t('capitalMarkets.securitiesPages')}>
                  <button disabled={page <= 1} onClick={() => setPage(page - 1)}>
                    {' '}
                    {t('capitalMarkets.anterior')}
                  </button>
                  <span aria-live="polite">
                    {formatNumber(
                      instruments.length ? (page - 1) * securities.data.page_size + 1 : 0,
                    )}{' '}
                    -{' '}
                    {formatNumber(
                      instruments.length
                        ? (page - 1) * securities.data.page_size + instruments.length
                        : 0,
                    )}{' '}
                    {t('capitalMarkets.de')} {formatNumber(securities.data.total)}
                  </span>
                  <button disabled={!securities.data.has_more} onClick={() => setPage(page + 1)}>
                    {' '}
                    {t('capitalMarkets.siguiente')}
                  </button>
                </nav>
              </>
            )}
          </>
        )}
      </SourceInformationCard>
      <MarketSourceInformation
        data={data}
        refresh={(source) => refresh.mutate(source)}
        refreshing={refresh.isPending}
        activeSource={refresh.variables}
        refreshError={refresh.error}
        refreshed={refresh.isSuccess}
      />
    </section>
  )
}
