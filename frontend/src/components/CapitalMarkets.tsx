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
import { FilterHelp } from './AdvancedFilters'
import { dateTime, registrationDate, issuanceMonth } from '../utils'

const registrationLabels: Record<RegistrationStatus, string> = {
  registered_active: 'Inscrito en RNVE',
  registered_cancelled: 'Inscripción cancelada',
  historical: 'Registro histórico',
  not_found_in_checked_source: 'Sin coincidencia en la fuente consultada',
  unknown: 'Registro no determinado',
}
const listingLabels: Record<ListingStatus, string> = {
  verified_listed: 'Listado verificado',
  verified_delisted: 'Deslistado verificado',
  not_found_in_checked_source: 'Sin coincidencia en la fuente consultada',
  unknown: 'Listado no verificado',
}
const availability: Record<string, string> = {
  not_yet_checked:
    'Valores aún no consultados para este emisor. No se ha ejecutado una consulta de instrumentos.',
  failed_to_retrieve:
    'Fuente temporalmente no disponible. La consulta falló; no significa ausencia de valores. Se reintentará al abrir Capital Markets después de 15 minutos.',
  stale:
    'Se muestran instrumentos de una observación anterior. Su vigencia requiere actualización.',
  available: '',
}
const date = (value: string | null) =>
  value ? (registrationDate(value)?.display ?? value) : 'No informado'

function PublicLink({ value }: { value: string | null | undefined }) {
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
  if (value !== null && value !== undefined && value !== '') return <>{value}</>
  if (issuer?.details_availability === 'available' || issuer?.details_availability === 'stale')
    return <MissingValue />
  return (
    <span
      className={`badge ${issuer?.details_availability === 'failed_to_retrieve' ? 'value-pill--missing' : 'value-pill--muted'}`}
    >
      {issuer?.details_availability === 'failed_to_retrieve' ? 'Unavailable' : 'Not yet checked'}
    </span>
  )
}

export function CapitalMarkets({ companyId }: { companyId: string }) {
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
  if ((data.common_equity_record_count ?? 0) > 1)
    alerts.push(
      <div className="notice danger" role="alert" key="multiple-common-equity">
        Se encontraron {data.common_equity_record_count} registros de Acciones ordinarias en Valores
        registrados. La consulta de cotizaciones está bloqueada hasta resolver la ambigüedad,
        independientemente del mercado, la paginación o los filtros.
      </div>,
    )
  if (refresh.isError)
    alerts.push(
      <RefreshAlert key="refresh-error" refresh={refreshData}>
        <strong>
          {data.sources.find((source) => source.id === refresh.variables)?.name ??
            refresh.variables}
        </strong>
        <p>{refresh.error.message} Los datos anteriores se conservan.</p>
      </RefreshAlert>,
    )
  if (data.rnve.match_status === 'potential')
    alerts.push(
      <RefreshAlert key="identity" refresh={refreshData}>
        Posible coincidencia de identidad pendiente de revisión. Los instrumentos del candidato no
        se atribuyen a esta empresa.
      </RefreshAlert>,
    )
  if (
    issuer &&
    ['stale', 'failed_to_retrieve'].includes(issuer.details_availability ?? '') &&
    !sourceAlerts.some((s) => s.id === 'sfc_rnve_issuer_details')
  )
    alerts.push(
      <RefreshAlert key="summary-details" refresh={refreshData}>
        <strong>SFC · Datos del emisor RNVE</strong>
        <p>
          {issuer.details_availability === 'failed_to_retrieve'
            ? 'No se pudo recuperar el resumen RNVE. No significa que los datos estén ausentes.'
            : 'Se conservan los últimos datos recuperados del RNVE.'}
        </p>
        <p>
          Última recuperación: {dateTime(issuer.administration_retrieved_at ?? null)} · Último
          intento: {dateTime(issuer.details_last_attempt_at ?? null)}
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
        <strong>SFC · Valores registrados</strong>
        <p>{availability[securities.data.availability]}</p>
      </RefreshAlert>,
    )
  return (
    <section className="capital-markets" aria-label="Capital Markets">
      <h2>Capital Markets</h2>
      {markets.isFetching && <Loading />}
      {refresh.isPending && <Loading />}
      {alerts.length > 0 && (
        <details className="panel market-alerts">
          <summary>Alertas ({alerts.length})</summary>
          {alerts}
        </details>
      )}
      <div className="profile-grid">
        <article className="panel">
          <h3>Registro Nacional de Valores y Emisores</h3>
          <span
            className={`badge ${data.rnve.status === 'registered_active' ? 'value-pill--present' : data.rnve.status === 'registered_cancelled' ? 'value-pill--missing' : 'value-pill--muted'}`}
          >
            {registrationLabels[data.rnve.status]}
          </span>
          {data.issuers.map((issuer) => (
            <div className="market-issuer" key={issuer.id}>
              <h4>{issuer.issuer_name}</h4>
              <dl>
                <div>
                  <dt>NIT normalizado</dt>
                  <dd>
                    {issuer.nit ?? 'No informado'}
                    {issuer.verification_digit ? `-${issuer.verification_digit}` : ''}
                  </dd>
                </div>
                <div>
                  <dt>Identificador original SFC</dt>
                  <dd>{issuer.source_nit ?? 'No informado'}</dd>
                </div>
                <div>
                  <dt>Tipo de entidad</dt>
                  <dd>
                    {issuer.regulator_entity_type ?? <MissingValue />} —{' '}
                    {issuer.regulator_entity_type_description ?? <MissingValue />}
                  </dd>
                </div>
                <div>
                  <dt>Código de entidad</dt>
                  <dd>{issuer.regulator_entity_code ?? <MissingValue />}</dd>
                </div>
                <div>
                  <dt>Verificado</dt>
                  <dd>{dateTime(issuer.last_verified_at)}</dd>
                </div>
                <div>
                  <dt>Identidad</dt>
                  <dd>
                    {issuer.match_status === 'verified'
                      ? 'NIT verificado'
                      : 'Coincidencia potencial'}
                  </dd>
                </div>
              </dl>
              <a className="text-link" href={issuer.source_url} target="_blank" rel="noreferrer">
                Fuente oficial RNVE ↗
              </a>
            </div>
          ))}
        </article>
        <article className="panel">
          <h3>Bolsa de Valores de Colombia</h3>
          {data.has_registered_bvc_common_equity ? (
            <div className="bvc-registration">
              <span className="badge value-pill--present">Registrado</span>
              <FilterHelp
                label="Registro BVC"
                text="Existe al menos un registro en Valores registrados con categoría Acciones ordinarias y mercado BVC. Se revisan todos los registros, sin depender de la paginación ni de los filtros. No indica negociación actual ni liquidez."
              />
            </div>
          ) : (
            <span
              className={`badge ${data.exchange_listing.status === 'verified_listed' ? 'value-pill--present' : 'value-pill--muted'}`}
            >
              {listingLabels[data.exchange_listing.status]}
            </span>
          )}
          {!data.exchange_listing.quotes?.length && (data.common_equity_record_count ?? 0) <= 1 && (
            <div className="notice danger" role="alert">
              No se ha establecido una coincidencia exacta por NIT, ANN o razón social con una
              cotización. Consulte otras fuentes; esto no confirma ausencia de acciones.
            </div>
          )}
          {(data.exchange_listing.quotes?.length ?? 0) > 0 ? (
            data.exchange_listing.quotes!.map((quote) => (
              <div className="bvc-quote" key={`${quote.source_id ?? 'bvc'}-${quote.instrument_id}`}>
                <div className="quote-heading">
                  <h4>
                    <span className="quote-ticker-label">
                      {quote.ticker ? 'Nemotécnico (ticker)' : 'Emisor'}
                    </span>
                    {quote.ticker ?? quote.reported_legal_name ?? <MissingValue />}
                  </h4>
                  {quote.stale && (
                    <span className="badge value-pill--review">Actualización pendiente</span>
                  )}
                </div>
                <div className="quote-highlight">
                  <div>
                    <span className="quote-label">
                      {quote.price_kind === 'daily_weighted_average'
                        ? 'Precio promedio ponderado diario'
                        : 'Último precio'}
                    </span>
                    <p className="bvc-price">
                      {quote.last_price !== null ? (
                        `${quote.currency ? `${quote.currency} ` : quote.raw_price?.includes('$') ? '$ ' : ''}${new Intl.NumberFormat('es-CO', { maximumFractionDigits: 2 }).format(Number(quote.last_price))}`
                      ) : (
                        <MissingValue />
                      )}
                    </p>
                  </div>
                  {quote.variation_percent != null && (
                    <div
                      className={`quote-change ${Number(quote.variation_percent) > 0 ? 'quote-up' : Number(quote.variation_percent) < 0 ? 'quote-down' : ''}`}
                    >
                      <span className="quote-label">Variación</span>
                      <strong>
                        {Number(quote.variation_percent) > 0
                          ? '↑ +'
                          : Number(quote.variation_percent) < 0
                            ? '↓ '
                            : ''}
                        {new Intl.NumberFormat('es-CO', { maximumFractionDigits: 2 }).format(
                          Number(quote.variation_percent),
                        )}
                        %
                      </strong>
                    </div>
                  )}
                </div>
                <p className="quote-date">
                  <span>Fecha del precio</span>
                  {quote.price_date
                    ? registrationDate(quote.price_date.replaceAll('-', ''))?.display
                    : quote.price_as_of
                      ? dateTime(quote.price_as_of)
                      : 'No informada'}
                </p>
                <dl className="quote-metrics">
                  {quote.volume != null && (
                    <div>
                      <dt>Volumen</dt>
                      <dd>
                        ${' '}
                        {new Intl.NumberFormat('es-CO', { maximumFractionDigits: 2 }).format(
                          Number(quote.volume),
                        )}
                      </dd>
                    </div>
                  )}
                  <div>
                    <dt>
                      {quote.source_id === 'la_republica_quotes'
                        ? 'ANN del registro RNVE'
                        : 'Código Superfinanciera'}
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
                    Fuente: {quote.source_name ?? 'Bolsa de Valores de Colombia'} ↗
                  </a>
                  <p>
                    Coincidencia:{' '}
                    {quote.match_type === 'exact_nit'
                      ? 'NIT exacto'
                      : quote.match_type === 'exact_legal_name'
                        ? 'Razón social EXACTA'
                        : 'ANN exacto'}{' '}
                    · {quote.matched_value ?? quote.superfinanciera_code}
                  </p>
                  <p>Recuperado: {dateTime(quote.retrieved_at)}</p>
                  {quote.source_note && <p className="quote-source-note">{quote.source_note}</p>}
                </div>
              </div>
            ))
          ) : (
            <dl>
              <div>
                <dt>Último precio</dt>
                <dd>
                  <span className="badge value-pill--muted">No verificado</span>
                </dd>
              </div>
              <div>
                <dt>Nemotécnico (ticker)</dt>
                <dd>
                  <span className="badge value-pill--muted">No verificado</span>
                </dd>
              </div>
            </dl>
          )}
          {(data.exchange_listing.attempts?.length ?? 0) > 0 && (
            <details className="quote-attempts" open={!data.exchange_listing.quotes?.length}>
              <summary>Fuentes de cotización ({data.exchange_listing.attempts!.length})</summary>
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
                            matched: 'Coincidencia exacta',
                            no_exact_match: 'Sin identidad verificable',
                            unavailable: 'No disponible',
                            not_configured: 'Sin ruta verificada',
                            not_checked: 'No consultada',
                          } as Record<string, string>
                        )[attempt.status] ?? attempt.status}
                      </span>
                    </div>
                    {attempt.detail && (
                      <p>{sourceErrorDescription(attempt.detail) ?? attempt.detail}</p>
                    )}
                    {attempt.last_attempt_at && (
                      <p>Último intento: {dateTime(attempt.last_attempt_at)}</p>
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
          <h3>Datos de contacto</h3>
          <dl>
            {(
              [
                ['Correo institucional', issuer?.contacts?.institutional_email],
                ['Dirección', issuer?.contacts?.address],
                ['Ciudad', issuer?.contacts?.city],
                ['Teléfono', issuer?.contacts?.phone],
              ] as const
            ).map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value || <MissingValue />}</dd>
              </div>
            ))}
            <div>
              <dt>Web</dt>
              <dd>
                <PublicLink value={issuer?.contacts?.website} />
              </dd>
            </div>
            <div>
              <dt>Redes Sociales</dt>
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
                Fuente RNVE ↗
              </a>{' '}
              · Obtenido: {dateTime(issuer.contacts_retrieved_at ?? null)}
            </p>
          )}
        </article>
        <article className="panel market-contact">
          <h3>Administración</h3>
          <dl>
            <div>
              <dt>Nro. Miembros Junta Directiva</dt>
              <dd>
                <AdministrationValue
                  value={issuer?.administration?.board_members_count}
                  issuer={issuer}
                />
              </dd>
            </div>
            <div>
              <dt>Representante Legal principal</dt>
              <dd>
                <AdministrationValue
                  value={issuer?.administration?.legal_representative}
                  issuer={issuer}
                />
              </dd>
            </div>
            <div>
              <dt>
                Representante Legal principal responsable de la informacion presentada al RNVE
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
                Fuente RNVE ↗
              </a>{' '}
              · Obtenido: {dateTime(issuer.administration_retrieved_at ?? null)}
            </p>
          )}
        </article>
      </div>
      <SourceInformationCard
        title={`Valores registrados${securities.data ? ` (${securities.data.unfiltered_total})` : ''}`}
        id="registered-securities"
      >
        {!verified ? (
          <p>
            {data.rnve.match_status === 'potential'
              ? 'Verifique primero la identidad del emisor candidato.'
              : 'No hay un vínculo de identidad verificado para atribuir instrumentos. Esto no demuestra que la empresa nunca haya emitido valores.'}
          </p>
        ) : (
          <>
            <div className="market-filters">
              <label>
                Categoría
                <select
                  value={category}
                  onChange={(event) => {
                    setCategory(event.target.value)
                    setPage(1)
                  }}
                >
                  <option value="">Todas</option>
                  {Object.entries(categories).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Mercado registrado
                <select
                  value={exchange}
                  onChange={(event) => {
                    setExchange(event.target.value)
                    setPage(1)
                  }}
                >
                  <option value="">Todos</option>
                  <option value="BVC">BVC (según SFC)</option>
                </select>
              </label>
              <label>
                Estado de listado
                <select
                  value={listingStatus}
                  onChange={(event) => {
                    setListingStatus(event.target.value)
                    setPage(1)
                  }}
                >
                  <option value="">Todos</option>
                  {Object.entries(listingLabels).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
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
                  {securities.data.total}{' '}
                  {securities.data.total === 1 ? 'record found' : 'records found'}
                </p>
                {instruments.length ? (
                  <div className="table-wrap">
                    <table className="instruments-table">
                      <thead>
                        <tr>
                          <th>Instrumento / categoría</th>
                          <th>Identificadores</th>
                          <th>Mercado registrado</th>
                          <th>Fechas de inscripción</th>
                          <th>Estado</th>
                          <th>Importe</th>
                          <th>Calificación reportada</th>
                          <th>Fuente</th>
                        </tr>
                      </thead>
                      <tbody>
                        {instruments.map((instrument) => (
                          <tr key={instrument.id}>
                            <td>
                              <strong>{instrument.security_name}</strong>
                              <p>{categories[instrument.security_category]}</p>
                              <span className="muted small">
                                Emisión: {issuanceMonth(instrument.issuance_number)}
                              </span>
                            </td>
                            <td>
                              {instrument.ticker && <p>Ticker: {instrument.ticker}</p>}
                              {instrument.isin && <p>ISIN: {instrument.isin}</p>}
                              <p>ANN: {instrument.ann_code ?? 'No informado'}</p>
                              {!instrument.ticker && (
                                <span className="muted small">Ticker no informado</span>
                              )}
                            </td>
                            <td>{instrument.exchange ?? 'RNVE; bolsa no informada'}</td>
                            <td>
                              <p>RNVE: {date(instrument.rnve_registration_date)}</p>
                              <p>BVC: {date(instrument.bvc_registration_date)}</p>
                            </td>
                            <td>
                              {listingLabels[instrument.listing_status]}
                              {instrument.quality_notes?.map((note) => (
                                <p className="badge value-pill--review" key={note}>
                                  {note}
                                </p>
                              ))}
                              {instrument.stale && (
                                <p className="badge value-pill--review">Observación anterior</p>
                              )}
                            </td>
                            <td>
                              {instrument.authorized_amount === null
                                ? 'Importe no informado'
                                : `${instrument.currency ?? ''} ${instrument.authorized_amount}`}
                            </td>
                            <td>{instrument.credit_rating || 'No informada'}</td>
                            <td>
                              <a
                                className="text-link"
                                href={instrument.source_url}
                                target="_blank"
                                rel="noreferrer"
                              >
                                SFC ↗
                              </a>
                              <p className="small muted">
                                Obtenido: {dateTime(instrument.last_verified_at)}
                              </p>
                              <details>
                                <summary>Valores originales SFC</summary>
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
                      ? 'No hay instrumentos en el reporte consultado que satisfagan estos filtros. No descarta emisiones históricas.'
                      : 'No se presenta una conclusión negativa sobre instrumentos.'}
                  </p>
                )}
                <nav className="pagination" aria-label="Securities pages">
                  <button disabled={page <= 1} onClick={() => setPage(page - 1)}>
                    ← Anterior
                  </button>
                  <span aria-live="polite">
                    {instruments.length ? (page - 1) * securities.data.page_size + 1 : 0} -{' '}
                    {instruments.length
                      ? (page - 1) * securities.data.page_size + instruments.length
                      : 0}{' '}
                    de {securities.data.total}
                  </span>
                  <button disabled={!securities.data.has_more} onClick={() => setPage(page + 1)}>
                    Siguiente →
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
