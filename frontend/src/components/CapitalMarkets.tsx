import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { categories, type ListingStatus, type RegistrationStatus } from '../types/capitalMarkets'
import { Failure, Loading } from './Feedback'
import { dateTime, registrationDate } from '../utils'

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
    'Fuente temporalmente no disponible. La consulta falló; no significa ausencia de valores.',
  stale:
    'Se muestran instrumentos de una observación anterior. Su vigencia requiere actualización.',
  available:
    'Instrumentos de la fuente SFC consultada. Su registro no verifica negociación vigente.',
}
const date = (value: string | null) =>
  value ? (registrationDate(value)?.display ?? value) : 'No informado'

export function CapitalMarkets({ companyId }: { companyId: string }) {
  const [page, setPage] = useState(1)
  const [category, setCategory] = useState('')
  const [exchange, setExchange] = useState('')
  const [listingStatus, setListingStatus] = useState('')
  const markets = useQuery({
    queryKey: ['capital-markets', companyId],
    queryFn: ({ signal }) => api.capitalMarkets(companyId, signal),
    staleTime: 5 * 60_000,
  })
  const securities = useQuery({
    queryKey: ['securities', companyId, page, category, exchange, listingStatus],
    queryFn: ({ signal }) =>
      api.securities(companyId, page, category, exchange, listingStatus, signal),
    enabled: markets.isSuccess && markets.data.rnve.match_status === 'verified',
    staleTime: 5 * 60_000,
  })
  if (markets.isPending) return <Loading />
  if (markets.isError) return <Failure error={markets.error} retry={() => void markets.refetch()} />
  const data = markets.data
  const verified = data.rnve.match_status === 'verified'
  const instruments = securities.data?.items ?? []
  return (
    <section className="capital-markets" aria-label="Capital Markets">
      <h2>Capital Markets</h2>
      <div className="notice" aria-label="Resumen de evidencia">
        <p>{data.summary}</p>
      </div>
      {data.stale && (
        <p className="notice warning" role="status">
          Evidencia desactualizada o última actualización fallida. Se conserva el último registro
          verificado.
        </p>
      )}
      <div className="profile-grid">
        <article className="panel">
          <h3>Registro Nacional de Valores y Emisores</h3>
          <span
            className={`badge ${data.rnve.status === 'registered_active' ? 'value-pill--present' : data.rnve.status === 'registered_cancelled' ? 'value-pill--missing' : 'value-pill--muted'}`}
          >
            {registrationLabels[data.rnve.status]}
          </span>
          {data.rnve.match_status === 'potential' && (
            <p className="notice warning">
              Posible coincidencia de identidad pendiente de revisión. Los instrumentos del
              candidato no se atribuyen a esta empresa.
            </p>
          )}
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
                  <dt>Tipo / código de entidad</dt>
                  <dd>
                    {issuer.regulator_entity_type} / {issuer.regulator_entity_code}
                  </dd>
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
          <p className="small muted">
            Propiedad: no evaluada. La forma jurídica se consulta en Overview y no determina
            propiedad pública o privada.
          </p>
        </article>
        <article className="panel">
          <h3>Bolsa de Valores de Colombia</h3>
          <span className="badge value-pill--muted">
            {listingLabels[data.exchange_listing.status]}
          </span>
          <p className="market-explanation">{data.exchange_listing.explanation}</p>
          <dl>
            <div>
              <dt>Acciones listadas</dt>
              <dd>
                {data.equity_listed === null
                  ? 'No verificado'
                  : data.equity_listed
                    ? 'Verificado'
                    : 'Sin coincidencia en la fuente consultada'}
              </dd>
            </div>
            <div>
              <dt>Fuente BVC</dt>
              <dd>
                {data.exchange_listing.availability === 'requires_authorized_source'
                  ? 'Requiere una fuente autorizada'
                  : data.exchange_listing.availability}
              </dd>
            </div>
          </dl>
          <p className="small muted">
            Una inscripción RNVE o una fecha BVC reportada por SFC no verifica cotización actual ni
            liquidez.
          </p>
        </article>
      </div>
      <article className="panel">
        <h3>Valores registrados</h3>
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
                <p className="market-explanation">
                  {availability[securities.data.availability] ?? securities.data.availability}
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
                          <th>Estado / importe</th>
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
                                Emisión: {instrument.issuance_number ?? 'No informada'}
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
                              <p>
                                {instrument.authorized_amount === null
                                  ? 'Importe no informado'
                                  : `${instrument.currency ?? ''} ${instrument.authorized_amount}`}
                              </p>
                              {instrument.credit_rating && (
                                <p>Calificación reportada: {instrument.credit_rating}</p>
                              )}
                            </td>
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
                  <span>Página {page}</span>
                  <button disabled={!securities.data.has_more} onClick={() => setPage(page + 1)}>
                    Siguiente →
                  </button>
                </nav>
              </>
            )}
          </>
        )}
      </article>
      <article className="panel">
        <h3>Fuentes y verificación</h3>
        {data.sources.map((source) => (
          <div className="market-source" key={source.id}>
            <h4>{source.name}</h4>
            <p>{source.institution}</p>
            <p>
              {source.availability === 'failed_to_retrieve'
                ? 'Fuente temporalmente no disponible'
                : source.availability === 'not_yet_checked'
                  ? 'Fuente aún no consultada'
                  : source.availability === 'requires_authorized_source'
                    ? 'Requiere una fuente autorizada'
                    : source.stale
                      ? 'Snapshot desactualizado'
                      : 'Snapshot disponible'}
            </p>
            {source.id === 'sfc_rnve' && source.latest_snapshot && (
              <p>
                {source.latest_snapshot.complete_current
                  ? 'Cobertura: directorio vigente completo confirmado al importar.'
                  : 'Cobertura: parcial o no certificada; no permite conclusiones negativas.'}
              </p>
            )}
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
            <a className="text-link" href={source.source_url} target="_blank" rel="noreferrer">
              Fuente oficial ↗
            </a>
          </div>
        ))}
        <ul className="market-limitations">
          {data.limitations.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </article>
    </section>
  )
}
