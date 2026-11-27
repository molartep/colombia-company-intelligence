import { useRefreshFeedback } from '../hooks/useRefreshFeedback'
import { ContractDetail, SourceLink } from './ContractDetail'
import { GovernmentInvolvement } from './GovernmentInvolvement'
import { Dropdown } from './Dropdown'
import { useCurrencyAmounts, useContractExport } from '../presentation/context'
import { uiMessage, errorMessage } from '../i18n/messages'
import { formatDate, formatNumber } from '../i18n/format'
import { locale, t, useLanguage } from '../i18n'
import { useLayoutEffect, useRef, useState } from 'react'
import { FitMetricValue } from './FitMetricValue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { ActivityGroup, ContractPage, SecopScreening } from '../types/secop'
import { Failure, Loading } from './Feedback'

const states = (): Record<SecopScreening['outcome'], string> => ({
  not_screened: t('governmentContracts.aunNoConsultadoEjecutaUnaConsultaParaRevisarEstaFuente'),
  running: t('governmentContracts.consultandoSecopIi'),
  missing_nit: t('governmentContracts.consultaNoDisponibleLaEmpresaNecesitaUnNitBaseConfirmado'),
  completed_with_matches: t('governmentContracts.consultaCompletadaConContratosVerificados'),
  completed_no_matches: t(
    'governmentContracts.noSeEncontraronContratosVerificadosEnEsteConjuntoDeDatos',
  ),
  source_unavailable: t(
    'governmentContracts.fuenteNoDisponibleNoSePudoComprobarSiExistenContratos',
  ),
  failed: t('governmentContracts.laConsultaNoSePudoCompletarNoHayUnaConclusion'),
  stale: t(
    'governmentContracts.datosAnterioresRequierenActualizacionSeConservaLaUltimaConsultaExitosa',
  ),
})
const shown = (value: string | null | undefined) => value || t('governmentContracts.noInformado')
// Explicit SECOP display exceptions. Raw filter values and evidence are preserved.
const sourceValue = (value: string | null | undefined) => shown(value).toLocaleUpperCase('es-CO')
const alphabetical = (groups: ActivityGroup[]) => {
  const collator = new Intl.Collator(locale(), { sensitivity: 'base' })
  return [...groups].sort((a, b) => collator.compare(sourceValue(a.label), sourceValue(b.label)))
}
const singleCurrency = (totals: Record<string, string>) =>
  Object.keys(totals).length === 1 ? Object.keys(totals)[0] : undefined
const currencyLabel = (label: string, currency?: string) =>
  currency ? `${label} (${currency})` : label
const timestamp = (value: string | null) =>
  value ? formatDate(value, true) : t('governmentContracts.sinConsulta')
function values(
  totals: Record<string, string>,
  money: ReturnType<typeof useCurrencyAmounts>,
  currency?: string,
) {
  const entries = Object.entries(totals)
  return entries.length
    ? entries.map(([code, amount]) => money.format(amount, code, code === currency)).join(' · ')
    : t('governmentContracts.noDisponibleSinValoresValidos')
}
function QuerySummary({ summary }: { summary: NonNullable<SecopScreening['summary']> }) {
  useLanguage()
  const money = useCurrencyAmounts()
  const currency = singleCurrency(summary.total_values)

  return (
    <aside className="secop-summary" aria-label={t('governmentContracts.resumenDeLaConsultaSecop')}>
      <h3>{t('governmentContracts.resumenDeLaConsulta')}</h3>
      <div className="secop-kpis">
        {(
          [
            [t('governmentContracts.totalContratos'), formatNumber(summary.total_contracts)],
            [
              currencyLabel(
                t('governmentContracts.valorContractualTotal'),
                money.currency(currency) ?? undefined,
              ),
              values(summary.total_values, money, currency),
            ],
            [t('governmentContracts.entidadesContratantes'), formatNumber(summary.distinct_buyers)],
            [t('governmentContracts.firmaMasReciente'), formatDate(summary.latest_signature_date)],
          ] as const
        ).map(([name, value]) => (
          <article className="panel" key={name}>
            <h4>{name}</h4>
            <FitMetricValue value={value} />
          </article>
        ))}
      </div>
    </aside>
  )
}
function Activity({
  title,
  groups,
  monetary = false,
  sourceLabels = false,
  currency,
}: {
  title: string
  groups: ActivityGroup[]
  monetary?: boolean
  sourceLabels?: boolean
  currency?: string
}) {
  useLanguage()
  const money = useCurrencyAmounts()

  const units = (value: string) => {
    const [whole = '0', fraction = ''] = value.split('.')
    return BigInt(whole) * 1000000n + BigInt(fraction.padEnd(6, '0').slice(0, 6))
  }
  const amounts = groups.map((g) => units((currency ? g.values[currency] : undefined) ?? '0'))
  const maxAmount = amounts.reduce((max, value) => (value > max ? value : max), 1n)
  const heights =
    monetary && currency
      ? amounts.map((value) => Number((value * 10000n) / maxAmount))
      : groups.map((g) => g.count)
  const max = monetary && currency ? 10000 : Math.max(1, ...heights)
  return (
    <article className="panel">
      <h3>{title}</h3>
      {!monetary && groups.some((g) => Object.keys(g.values).length > 0) && (
        <p className="small muted">
          {currencyLabel(
            t('governmentContracts.valorContractualTotal'),
            money.currency(currency) ?? undefined,
          )}
        </p>
      )}
      {groups.length ? (
        <ul className="secop-bars">
          {groups.map((g, index) => (
            <li key={g.label}>
              <div>
                <span>{sourceLabels ? sourceValue(g.label) : uiMessage(g.label)}</span>
                {!monetary && <strong>{formatNumber(g.count)}</strong>}
              </div>
              {monetary && (
                <p className="currency-value">
                  <strong>{values(g.values, money, currency)}</strong>
                </p>
              )}
              {(!monetary || currency) && (
                <meter
                  min={0}
                  max={max}
                  value={heights[index] ?? 0}
                  aria-label={
                    monetary
                      ? `${sourceLabels ? sourceValue(g.label) : uiMessage(g.label)}: ${values(g.values, money, currency)}`
                      : t('governmentContracts.valueValueContratos', {
                          value0: sourceLabels ? sourceValue(g.label) : uiMessage(g.label),
                          count: g.count,
                        })
                  }
                />
              )}
              {monetary ? (
                <small>{t('common.contractCount', { count: g.count })}</small>
              ) : (
                Object.keys(g.values).length > 0 && (
                  <small className="currency-value">{values(g.values, money, currency)}</small>
                )
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p>{t('governmentContracts.sinDatosParaEstaConsulta')}</p>
      )}
    </article>
  )
}
function Contracts({ companyId, screening }: { companyId: string; screening: SecopScreening }) {
  useLanguage()
  const money = useCurrencyAmounts()

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
  const query = useQuery<ContractPage>({
    queryKey: ['secop-contracts', companyId, params.toString()],
    // Preserve layout while changing filters/pages, only within the same company/run.
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === companyId && previous?.run_id === screening.run_id
        ? previous
        : undefined,
    queryFn: ({ signal }) => api.secopContracts(companyId, params, signal),
  })
  useContractExport(companyId, params.toString(), query.isFetching || query.isError || !query.data)
  const tableViewport = useRef<HTMLDivElement>(null)
  const tableHeight = useRef(0)
  useLayoutEffect(() => {
    const viewport = tableViewport.current
    if (!viewport) return
    tableHeight.current = Math.max(tableHeight.current, viewport.getBoundingClientRect().height)
    viewport.style.setProperty('--contracts-table-height', `${tableHeight.current}px`)
  }, [query.data])
  const summary = screening.summary!
  const candidateCurrency = singleCurrency(summary.total_values)
  const currency =
    candidateCurrency &&
    query.data?.items.every((c) => c.value === null || c.currency === candidateCurrency)
      ? candidateCurrency
      : undefined
  const change = (key: keyof typeof filters, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }))
    setPage(1)
  }
  return (
    <section className="panel">
      <h3>{t('governmentContracts.contratosVerificados')}</h3>
      <div className="market-filters">
        <label>
          {' '}
          {t('governmentContracts.buscarContrato')}{' '}
          <input value={filters.q} maxLength={160} onChange={(e) => change('q', e.target.value)} />
        </label>
        <label>
          {' '}
          {t('governmentContracts.entidadNombreExacto')}{' '}
          <Dropdown
            editable
            aria-label={t('governmentContracts.entidadNombreExacto')}
            value={filters.entity}
            className="secop-source-field"
            maxLength={1000}
            options={alphabetical(summary.top_buyers).map((g) => ({
              value: g.label,
              label: sourceValue(g.label),
            }))}
            onChange={(value) => {
              const original = summary.top_buyers.find(
                (g) => g.label.toLocaleUpperCase('es-CO') === value.toLocaleUpperCase('es-CO'),
              )?.label
              change('entity', original ?? value)
            }}
          />
        </label>
        {(
          [
            [
              'status',
              t('governmentContracts.estado'),
              alphabetical(summary.statuses).map((g) => ({
                value: g.label,
                label: sourceValue(g.label),
              })),
            ],
            [
              'year',
              t('governmentContracts.anoDeFirma'),
              summary.annual
                .filter((g) => /^\d{4}$/.test(g.label))
                .map((g) => ({ value: g.label, label: g.label })),
            ],
            [
              'modality',
              t('governmentContracts.modalidad'),
              alphabetical(summary.modalities).map((g) => ({
                value: g.label,
                label: sourceValue(g.label),
              })),
            ],
          ] as const
        ).map(([key, label, options]) => (
          <label key={key}>
            {label}
            <Dropdown
              aria-label={label}
              value={filters[key]}
              onChange={(value) => change(key, value)}
              options={[
                ...(key === 'year'
                  ? [{ value: 'missing', label: t('governmentContracts.sinFechaDeFirma') }]
                  : []),
                { value: '', label: t('governmentContracts.todos') },
                ...options,
              ]}
            />
          </label>
        ))}
        <div className="secop-sort-field">
          <label htmlFor="secop-sort">{t('governmentContracts.ordenarPor')}</label>
          <div className="secop-sort-control">
            <Dropdown
              id="secop-sort"
              aria-label={t('governmentContracts.ordenarPor')}
              value={filters.sort}
              onChange={(value) => change('sort', value)}
              options={[
                { value: 'date', label: t('governmentContracts.fechaDeFirma') },
                { value: 'value', label: t('governmentContracts.valorReportado') },
              ]}
            />
            <button
              className="refresh-button"
              type="button"
              aria-label={
                filters.direction === 'desc'
                  ? t('governmentContracts.ordenDescendenteCambiarAAscendente')
                  : t('governmentContracts.ordenAscendenteCambiarADescendente')
              }
              title={
                filters.direction === 'desc'
                  ? t('governmentContracts.cambiarAAscendente')
                  : t('governmentContracts.cambiarADescendente')
              }
              onClick={() => change('direction', filters.direction === 'desc' ? 'asc' : 'desc')}
            >
              <span aria-hidden="true">{filters.direction === 'desc' ? '↓' : '↑'}</span>
            </button>
          </div>
        </div>
      </div>
      <p className="small muted contracts-query-status" role="status" aria-live="polite">
        {query.isPlaceholderData ? t('governmentContracts.updatingPreviousResults') : ''}
      </p>
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <Failure error={query.error} retry={() => void query.refetch()} />
      ) : (
        <>
          <p className="small muted">{t('common.contractsFound', { count: query.data.total })}</p>
          <p className="table-scroll-hint" id="contracts-scroll-hint">
            {t('common.scrollTable')}
          </p>
          <div
            className={`table-wrap secop-table-wrap${query.data.items.length ? '' : ' is-empty'}`}
            ref={tableViewport}
            aria-busy={query.isFetching}
            aria-describedby="contracts-scroll-hint"
            tabIndex={0}
            role="region"
            aria-label={t('governmentContracts.tablaDeContratosVerificados')}
          >
            <table className="instruments-table secop-contracts-table">
              <thead>
                <tr>
                  {[
                    t('governmentContracts.contratoReferencia'),
                    t('governmentContracts.entidad'),
                    t('governmentContracts.descripcion'),
                    currencyLabel(
                      t('governmentContracts.valor'),
                      money.currency(currency) ?? undefined,
                    ),
                    t('governmentContracts.firma'),
                    t('governmentContracts.estado'),
                    t('governmentContracts.modalidad'),
                    t('governmentContracts.fuente'),
                  ].map((h, index) => (
                    <th key={h} scope="col" className={index === 3 ? 'numeric-cell' : undefined}>
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
                    <td>{sourceValue(c.buyer)}</td>
                    <td>{shown(c.description)}</td>
                    <td className="numeric-cell">
                      {c.value === null
                        ? t('governmentContracts.noInformado')
                        : money.format(
                            c.value,
                            c.currency ?? t('governmentContracts.monedaNoInformada'),
                            c.currency === currency,
                            true,
                          )}
                    </td>
                    <td className="date-cell">{formatDate(c.signature_date)}</td>
                    <td>{sourceValue(c.raw_status)}</td>
                    <td>{sourceValue(c.modality)}</td>
                    <td>
                      <SourceLink contract={c} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!query.data.items.length && (
              <p className="secop-table-empty">
                {t('governmentContracts.noHayContratosQueCoincidanConEstosFiltros')}
              </p>
            )}
          </div>
          <nav className="pagination" aria-label={t('governmentContracts.paginasDeContratos')}>
            <button
              disabled={query.isPlaceholderData || page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              {' '}
              {t('governmentContracts.anterior')}
            </button>
            <span aria-live="polite">
              {formatNumber(
                query.data.items.length ? (query.data.page - 1) * query.data.page_size + 1 : 0,
              )}{' '}
              -{' '}
              {formatNumber(
                query.data.items.length
                  ? (query.data.page - 1) * query.data.page_size + query.data.items.length
                  : 0,
              )}{' '}
              {t('governmentContracts.de')} {formatNumber(query.data.total)}
            </span>
            <button
              disabled={query.isPlaceholderData || !query.data.has_more}
              onClick={() => setPage((p) => p + 1)}
            >
              {' '}
              {t('governmentContracts.siguiente')}
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
  useLanguage()
  const money = useCurrencyAmounts()

  const client = useQueryClient()
  const query = useQuery({
    queryKey: ['secop', companyId],
    queryFn: ({ signal }) => api.secop(companyId, signal),
    refetchInterval: (query) => (query.state.data?.outcome === 'running' ? 2000 : false),
  })
  const feedback = useRefreshFeedback()
  const refresh = useMutation({
    onError: feedback.onError,
    mutationFn: () => api.refreshSecop(companyId),
    onSuccess: async (data) => {
      client.setQueryData(['secop', companyId], data)
      await client.invalidateQueries({ queryKey: ['secop-contracts', companyId] })
      await client.invalidateQueries({ queryKey: ['secop-detail', companyId] })
      await client.invalidateQueries({ queryKey: ['involvement', companyId] })
    },
  })
  if (query.isPending) return <Loading />
  if (query.isError) return <Failure error={query.error} retry={() => void query.refetch()} />
  const data = query.data
  const summary = data.summary
  const currency = summary ? singleCurrency(summary.total_values) : undefined
  return (
    <div className="secop-module">
      <article className={`panel${summary ? ' secop-header-with-summary' : ''}`}>
        <div className="secop-header-main">
          <p className="eyebrow">{t('governmentContracts.governmentContractsSecopIi')}</p>
          <h2>{t('governmentContracts.secopIiContratacionPublica')}</h2>
          <p>
            <strong>{data.company_name}</strong> {t('governmentContracts.nit')}{' '}
            {data.nit ?? t('governmentContracts.noConfirmado')}
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
              ? t('governmentContracts.consultandoSecopIiLaConsultaPuedeTardarHasta90Segundos')
              : states()[data.outcome]}
          </p>
          {data.error_code === 'secop_limit_exceeded' && (
            <div role="alert" className="secop-warning">
              <strong>{t('governmentContracts.laConsultaSuperaElLimiteDe5000Registros')}</strong>
              <p> {t('governmentContracts.estePortafolioExcedeElLimiteActualDeLaConsultaSecop')}</p>
              {summary && (
                <p>
                  {' '}
                  {t(
                    'governmentContracts.seConservanLosResultadosDeLaUltimaConsultaExitosaPendientes',
                  )}
                </p>
              )}
            </div>
          )}
          {refresh.isError && (
            <p role="alert">{feedback.message(refresh.error) ?? errorMessage(refresh.error)}</p>
          )}
          <p className="small muted">
            {' '}
            {t('governmentContracts.ultimaConsultaExitosa')} {timestamp(data.last_successful_at)}
            <br /> {t('governmentContracts.ultimoIntento')} {timestamp(data.last_attempted_at)}
            <br /> {t('governmentContracts.actualizacionDelConjunto')}{' '}
            {timestamp(data.source_updated_at)}
            {data.cache_age_seconds !== null && (
              <>
                <br /> {t('governmentContracts.cache')}{' '}
                {formatNumber(Math.floor(data.cache_age_seconds / 60))}{' '}
                {t('governmentContracts.minutosVigencia')}{' '}
                {formatNumber(data.cache_ttl_seconds / 3600)} {t('governmentContracts.horas')}
              </>
            )}
          </p>
          <a className="text-link" href={data.source_url} target="_blank" rel="noreferrer">
            {' '}
            {t('governmentContracts.conjuntoDeDatosOficial')}
          </a>
          <p className="small">{data.publisher}</p>
          <button
            className="refresh-button"
            aria-busy={refresh.isPending}
            disabled={
              refresh.isPending ||
              feedback.seconds > 0 ||
              data.outcome === 'missing_nit' ||
              data.outcome === 'running'
            }
            onClick={() => refresh.mutate()}
          >
            {feedback.seconds > 0
              ? t('common.refreshInSeconds', { count: feedback.seconds })
              : data.last_attempted_at
                ? t('governmentContracts.actualizarConsulta')
                : t('governmentContracts.consultarSecop')}
          </button>
        </div>
        {summary && <QuerySummary summary={summary} />}
      </article>
      {summary && (
        <>
          <p className="small muted">
            {t('common.contractsIncluded', { count: summary.monetary_contracts })} ·{' '}
            {summary.unknown_currency_contracts > 0 && (
              <>
                {formatNumber(summary.unknown_currency_contracts)}{' '}
                {t('governmentContracts.sinMoneda')}
              </>
            )}
            {summary.missing_or_invalid_values > 0 && (
              <>
                {formatNumber(summary.missing_or_invalid_values)}{' '}
                {t('governmentContracts.sinValorValido3')}
              </>
            )}
            {formatNumber(summary.zero_value_contracts)} {t('governmentContracts.conValorCero')}
          </p>
          <div className="profile-grid secop-insights-grid">
            <GovernmentInvolvement companyId={companyId} runId={data.run_id} />
            <Activity
              title={t('governmentContracts.contratosPorEstado')}
              groups={alphabetical(summary.statuses)}
              currency={currency}
              sourceLabels
            />
            <Activity
              title={currencyLabel(
                t('governmentContracts.annualContractValue'),
                money.currency(currency) ?? undefined,
              )}
              groups={summary.annual}
              currency={currency}
              monetary
            />
            <Activity
              title={currencyLabel(
                t('governmentContracts.topFiveBuyersByValue'),
                money.currency(currency) ?? undefined,
              )}
              groups={summary.top_buyers}
              currency={currency}
              sourceLabels
              monetary
            />
          </div>
          <p className="small muted">
            {' '}
            {t('governmentContracts.valoresExpresadosEnPesosColombianosCopPorConfiguracionDeLa')}
          </p>
          <Contracts key={data.run_id} companyId={companyId} screening={data} />
        </>
      )}
      {!summary && <GovernmentInvolvement companyId={companyId} runId={data.run_id} />}
      <details className="panel market-provenance">
        <summary>{t('governmentContracts.metodologiaYAlcance')}</summary>
        <ul className="market-limitations">
          <li>
            {' '}
            {t('governmentContracts.coincidenciaExactaDelNitDelProveedorNuncaPorSimilitudDe')}
          </li>
          {data.warnings.map((w) => (
            <li key={w}>{uiMessage(w)}</li>
          ))}
        </ul>
      </details>
    </div>
  )
}
