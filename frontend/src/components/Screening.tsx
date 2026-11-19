import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { ActivityGroup, Contract, SecopScreening } from '../types/secop'
import { Failure, Loading } from './Feedback'

const states: Record<SecopScreening['outcome'], string> = {
  not_screened: 'Aún no consultado. Ejecuta una consulta para revisar esta fuente.',
  running: 'Consultando SECOP II…',
  missing_nit:
    'Consulta no disponible: la empresa necesita un NIT base confirmado de nueve dígitos en la fuente de identidad.',
  completed_with_matches: 'Consulta completada con contratos verificados.',
  completed_no_matches:
    'No se encontraron contratos verificados en este conjunto de datos. Esto no significa que la empresa nunca haya contratado con el Estado.',
  source_unavailable: 'Fuente no disponible. No se pudo comprobar si existen contratos.',
  failed: 'La consulta no se pudo completar. No hay una conclusión sobre ausencia de contratos.',
  stale: 'Datos anteriores: requieren actualización. Se conserva la última consulta exitosa.',
}
const shown = (value: string | null | undefined) => value || 'No informado'
const uppercase = (value: string | null | undefined) => shown(value).toLocaleUpperCase('es-CO')
const timestamp = (value: string | null) =>
  value ? new Date(value).toLocaleString('es-CO', { timeZone: 'America/Bogota' }) : 'Sin consulta'
// Keep decimal strings intact; monetary values must not pass through binary floating point.
function decimal(value: string) {
  const [whole = '', fraction] = value.split('.')
  return whole.replace(/\B(?=(\d{3})+(?!\d))/g, '.') + (fraction ? `,${fraction}` : '')
}
function values(totals: Record<string, string>) {
  const entries = Object.entries(totals)
  return entries.length
    ? entries.map(([currency, amount]) => `${decimal(amount)} ${currency}`).join(' · ')
    : 'No disponible — sin valores válidos'
}
function QuerySummary({ summary }: { summary: NonNullable<SecopScreening['summary']> }) {
  return (
    <aside className="secop-summary" aria-label="Resumen de la consulta SECOP">
      <h3>Resumen de la consulta</h3>
      <div className="secop-kpis">
        {[
          ['Total contratos', summary.total_contracts],
          ['Valor contractual total', values(summary.total_values)],
          ['Entidades contratantes', summary.distinct_buyers],
          ['Firma más reciente', shown(summary.latest_signature_date)],
        ].map(([name, value]) => (
          <article className="panel" key={name}>
            <h4>{name}</h4>
            <strong>{value}</strong>
          </article>
        ))}
      </div>
    </aside>
  )
}
function SourceLink({ contract }: { contract: Contract }) {
  return (
    <a className="text-link" href={contract.source_url} target="_blank" rel="noreferrer">
      {contract.source_link_label} ↗
    </a>
  )
}
function Activity({
  title,
  groups,
  monetary = false,
  uppercaseLabels = false,
}: {
  title: string
  groups: ActivityGroup[]
  monetary?: boolean
  uppercaseLabels?: boolean
}) {
  const units = (value: string) => {
    const [whole = '0', fraction = ''] = value.split('.')
    return BigInt(whole) * 1000000n + BigInt(fraction.padEnd(6, '0').slice(0, 6))
  }
  const amounts = groups.map((g) => units(g.values.COP ?? '0'))
  const maxAmount = amounts.reduce((max, value) => (value > max ? value : max), 1n)
  const heights = monetary
    ? amounts.map((value) => Number((value * 10000n) / maxAmount))
    : groups.map((g) => g.count)
  const max = monetary ? 10000 : Math.max(1, ...heights)
  return (
    <article className="panel">
      <h3>{title}</h3>
      {groups.length ? (
        <ul className="secop-bars">
          {groups.map((g, index) => (
            <li key={g.label}>
              <div>
                <span>{uppercaseLabels ? uppercase(g.label) : g.label}</span>
                <strong>
                  {monetary
                    ? g.values.COP === undefined
                      ? 'Sin valor válido'
                      : `${decimal(g.values.COP)} COP`
                    : g.count}
                </strong>
              </div>
              <meter
                min={0}
                max={max}
                value={heights[index] ?? 0}
                aria-label={
                  monetary
                    ? `${uppercaseLabels ? uppercase(g.label) : g.label}: ${g.values.COP ?? 'sin valor válido'} COP`
                    : `${uppercaseLabels ? uppercase(g.label) : g.label}: ${g.count} contratos`
                }
              />
              {monetary ? (
                <small>{g.count} contratos</small>
              ) : (
                Object.keys(g.values).length > 0 && <small>{values(g.values)}</small>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p>Sin datos para esta consulta.</p>
      )}
    </article>
  )
}
function ContractDetail({
  companyId,
  id,
  runId,
  close,
}: {
  companyId: string
  id: string
  runId: string
  close: () => void
}) {
  const query = useQuery({
    queryKey: ['secop-detail', companyId, id, runId],
    queryFn: ({ signal }) => api.secopContract(companyId, id, signal, runId),
  })
  return (
    <section className="panel secop-detail" aria-label="Detalle del contrato">
      <button className="refresh-button" onClick={close}>
        Cerrar detalle
      </button>
      <h3>Detalle del contrato {id}</h3>
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <Failure error={query.error} retry={() => void query.refetch()} />
      ) : (
        <>
          <p>{shown(query.data.description)}</p>
          <dl>
            {Object.entries({
              Contrato: query.data.contract_id,
              Proceso: query.data.process_id,
              Referencia: query.data.reference,
              'Entidad contratante': uppercase(query.data.buyer),
              'NIT de la entidad': query.data.buyer_nit,
              'Documento original del proveedor': query.data.original_supplier_identifier,
              'NIT normalizado del proveedor': query.data.normalized_supplier_identifier,
              'Tipo de documento': query.data.supplier_document_type,
              Coincidencia: `${query.data.match_method} / ${query.data.match_status}`,
              'Valor reportado':
                query.data.value === null
                  ? null
                  : `${decimal(query.data.value)} ${query.data.currency ?? '(moneda no informada)'}`,
              'Estado en la fuente': uppercase(query.data.raw_status),
              'Tipo de contrato': query.data.contract_type,
              Modalidad: uppercase(query.data.modality),
              Firma: query.data.signature_date,
              Inicio: query.data.start_date,
              Fin: query.data.end_date,
              'Departamento de la entidad': query.data.department,
              'Ciudad de la entidad': query.data.city,
              'Fila de la fuente': query.data.source_identifier,
              Evidencia: query.data.evidence_id,
              Recuperado: timestamp(query.data.retrieved_at),
              'Actualización del contrato': query.data.source_updated_at,
            }).map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{shown(value)}</dd>
              </div>
            ))}
          </dl>
          <SourceLink contract={query.data} />
        </>
      )}
    </section>
  )
}
function Contracts({ companyId, screening }: { companyId: string; screening: SecopScreening }) {
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({
    q: '',
    status: '',
    entity: '',
    year: '',
    modality: '',
    sort: 'date',
    direction: 'desc',
  })
  const [detail, setDetail] = useState<string | null>(null)
  const params = new URLSearchParams({
    page: String(page),
    page_size: '5',
    run_id: screening.run_id ?? '',
  })
  Object.entries(filters).forEach(([key, value]) => {
    if (key === 'year' && value === 'missing') {
      params.set('missing_signature_date', 'true')
    } else if (value) {
      params.set(key === 'status' ? 'raw_status' : key, value)
    }
  })
  const query = useQuery({
    queryKey: ['secop-contracts', companyId, params.toString()],
    queryFn: ({ signal }) => api.secopContracts(companyId, params, signal),
  })
  const summary = screening.summary!
  const change = (key: keyof typeof filters, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }))
    setPage(1)
  }
  return (
    <section className="panel">
      <h3>Contratos verificados</h3>
      <div className="market-filters">
        <label>
          Buscar contrato
          <input value={filters.q} maxLength={160} onChange={(e) => change('q', e.target.value)} />
        </label>
        <label>
          Entidad (nombre exacto)
          <input
            className="secop-uppercase"
            value={filters.entity}
            maxLength={1000}
            list="secop-buyers"
            onChange={(e) => {
              const value = e.target.value
              const original = summary.top_buyers.find(
                (g) => uppercase(g.label) === uppercase(value),
              )?.label
              change('entity', original ?? value)
            }}
          />
          <datalist id="secop-buyers">
            {summary.top_buyers.map((g) => (
              <option key={g.label} value={uppercase(g.label)} />
            ))}
          </datalist>
        </label>
        {(
          [
            [
              'status',
              'Estado',
              summary.statuses.map((g) => ({
                value: g.label,
                label: uppercase(g.label),
              })),
            ],
            [
              'year',
              'Año de firma',
              summary.annual
                .filter((g) => /^\d{4}$/.test(g.label))
                .map((g) => ({ value: g.label, label: g.label })),
            ],
            [
              'modality',
              'Modalidad',
              summary.modalities.map((g) => ({ value: g.label, label: uppercase(g.label) })),
            ],
          ] as const
        ).map(([key, label, options]) => (
          <label key={key}>
            {label}
            <select value={filters[key]} onChange={(e) => change(key, e.target.value)}>
              {key === 'year' && <option value="missing">Sin fecha de firma</option>}
              <option value="">Todos</option>
              {options.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
        ))}
        <div className="secop-sort-field">
          <label htmlFor="secop-sort">Ordenar por</label>
          <div className="secop-sort-control">
            <select
              id="secop-sort"
              value={filters.sort}
              onChange={(e) => change('sort', e.target.value)}
            >
              <option value="date">Fecha de firma</option>
              <option value="value">Valor reportado</option>
            </select>
            <button
              className="refresh-button"
              type="button"
              aria-label={
                filters.direction === 'desc'
                  ? 'Orden descendente. Cambiar a ascendente'
                  : 'Orden ascendente. Cambiar a descendente'
              }
              title={
                filters.direction === 'desc' ? 'Cambiar a ascendente' : 'Cambiar a descendente'
              }
              onClick={() => change('direction', filters.direction === 'desc' ? 'asc' : 'desc')}
            >
              <span aria-hidden="true">{filters.direction === 'desc' ? '↓' : '↑'}</span>
            </button>
          </div>
        </div>
      </div>
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <Failure error={query.error} retry={() => void query.refetch()} />
      ) : (
        <>
          <p className="small muted">{query.data.total} contratos encontrados</p>
          <div
            className="table-wrap secop-table-wrap"
            tabIndex={0}
            role="region"
            aria-label="Tabla de contratos verificados"
          >
            <table className="instruments-table secop-contracts-table">
              <thead>
                <tr>
                  {[
                    'Contrato / referencia',
                    'Entidad',
                    'Descripción',
                    'Valor',
                    'Firma',
                    'Estado',
                    'Modalidad',
                    'Fuente',
                  ].map((h) => (
                    <th key={h} scope="col">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((c) => (
                  <tr key={c.contract_id}>
                    <td>
                      <button className="text-link" onClick={() => setDetail(c.contract_id)}>
                        {c.contract_id}
                      </button>
                      <p>{c.reference}</p>
                    </td>
                    <td>{uppercase(c.buyer)}</td>
                    <td>{shown(c.description)}</td>
                    <td>
                      {c.value === null
                        ? 'No informado'
                        : `${decimal(c.value)} ${c.currency ?? '(moneda no informada)'}`}
                    </td>
                    <td>{shown(c.signature_date)}</td>
                    <td>{uppercase(c.raw_status)}</td>
                    <td>{uppercase(c.modality)}</td>
                    <td>
                      <SourceLink contract={c} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!query.data.items.length && <p>No hay contratos que coincidan con estos filtros.</p>}
          <nav className="pagination" aria-label="Páginas de contratos">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              ← Anterior
            </button>
            <span aria-live="polite">
              {query.data.items.length ? (page - 1) * query.data.page_size + 1 : 0} -{' '}
              {query.data.items.length
                ? (page - 1) * query.data.page_size + query.data.items.length
                : 0}{' '}
              de {query.data.total}
            </span>
            <button disabled={!query.data.has_more} onClick={() => setPage((p) => p + 1)}>
              Siguiente →
            </button>
          </nav>
        </>
      )}
      {detail && (
        <ContractDetail
          companyId={companyId}
          id={detail}
          runId={screening.run_id ?? ''}
          close={() => setDetail(null)}
        />
      )}
    </section>
  )
}
export function Screening({ companyId }: { companyId: string }) {
  const client = useQueryClient()
  const query = useQuery({
    queryKey: ['secop', companyId],
    queryFn: ({ signal }) => api.secop(companyId, signal),
    refetchInterval: (query) => (query.state.data?.outcome === 'running' ? 2000 : false),
  })
  const refresh = useMutation({
    mutationFn: () => api.refreshSecop(companyId),
    onSuccess: async (data) => {
      client.setQueryData(['secop', companyId], data)
      await client.invalidateQueries({ queryKey: ['secop-contracts', companyId] })
      await client.invalidateQueries({ queryKey: ['secop-detail', companyId] })
    },
  })
  if (query.isPending) return <Loading />
  if (query.isError) return <Failure error={query.error} retry={() => void query.refetch()} />
  const data = query.data
  const summary = data.summary
  return (
    <div className="secop-module">
      <article className={`panel${summary ? ' secop-header-with-summary' : ''}`}>
        <div className="secop-header-main">
          <p className="eyebrow">GOVERNMENT CONTRACTS · SECOP II</p>
          <h2>SECOP II — Contratación Pública</h2>
          <p>
            <strong>{data.company_name}</strong> · NIT: {data.nit ?? 'No confirmado'}
          </p>
          <p
            role="status"
            className={
              ['stale', 'failed', 'source_unavailable'].includes(data.outcome)
                ? 'secop-warning'
                : ''
            }
          >
            {refresh.isPending
              ? 'Consultando SECOP II… La consulta puede tardar hasta 90 segundos.'
              : states[data.outcome]}
          </p>
          {data.error_code === 'secop_limit_exceeded' && (
            <div role="alert" className="secop-warning">
              <strong>La consulta supera el límite de 5.000 registros</strong>
              <p>
                Este portafolio excede el límite actual de la consulta SECOP. No se pudo completar
                la consulta y no se presentan totales parciales. Esto no significa ausencia de
                contratos.
              </p>
              {summary && (
                <p>
                  Se conservan los resultados de la última consulta exitosa, pendientes de
                  actualización.
                </p>
              )}
            </div>
          )}
          {refresh.isError && <p role="alert">{refresh.error.message}</p>}
          <p className="small muted">
            Última consulta exitosa: {timestamp(data.last_successful_at)}
            <br />
            Último intento: {timestamp(data.last_attempted_at)}
            <br />
            Actualización del conjunto: {timestamp(data.source_updated_at)}
            {data.cache_age_seconds !== null && (
              <>
                <br />
                Caché: {Math.floor(data.cache_age_seconds / 60)} minutos · vigencia{' '}
                {data.cache_ttl_seconds / 3600} horas
              </>
            )}
          </p>
          <a className="text-link" href={data.source_url} target="_blank" rel="noreferrer">
            Conjunto de datos oficial ↗
          </a>
          <p className="small">{data.publisher}</p>
          <button
            className="refresh-button"
            aria-busy={refresh.isPending}
            disabled={
              refresh.isPending || data.outcome === 'missing_nit' || data.outcome === 'running'
            }
            onClick={() => refresh.mutate()}
          >
            {data.last_attempted_at ? 'Actualizar consulta' : 'Consultar SECOP'}
          </button>
        </div>
        {summary && <QuerySummary summary={summary} />}
      </article>
      {summary && (
        <>
          <p className="small muted">
            {summary.monetary_contracts} contratos incluidos en sumas ·{' '}
            {summary.unknown_currency_contracts > 0 && (
              <>{summary.unknown_currency_contracts} sin moneda · </>
            )}
            {summary.missing_or_invalid_values > 0 && (
              <>{summary.missing_or_invalid_values} sin valor válido · </>
            )}
            {summary.zero_value_contracts} con valor cero.
          </p>
          <div className="profile-grid">
            <Activity title="Contratos por estado" groups={summary.statuses} uppercaseLabels />
            <Activity title="Valor contractual anual (COP)" groups={summary.annual} monetary />
            <Activity
              title="Cinco entidades por valor contractual (COP)"
              groups={summary.top_buyers}
              uppercaseLabels
              monetary
            />
          </div>
          <p className="small muted">
            Valores expresados en pesos colombianos (COP) por configuración de la aplicación. Son
            valores contractuales reportados, no pagos ni ingresos.
          </p>
          <Contracts key={data.run_id} companyId={companyId} screening={data} />
        </>
      )}
      <details className="panel market-provenance">
        <summary>Metodología y alcance</summary>
        <ul className="market-limitations">
          <li>
            Coincidencia exacta del NIT del proveedor, nunca por similitud de nombre ni por el NIT
            de la entidad compradora.
          </li>
          {data.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      </details>
    </div>
  )
}
