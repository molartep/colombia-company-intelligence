import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { vi } from 'vitest'
import { Screening } from './components/Screening'
import { api } from './api/client'
import type { Contract, SecopScreening } from './types/secop'

vi.mock('./api/client', () => ({
  api: { secop: vi.fn(), refreshSecop: vi.fn(), secopContracts: vi.fn(), secopContract: vi.fn() },
}))
const initial: SecopScreening = {
  company_id: 'company',
  company_name: 'SYNTHETIC SAS',
  nit: '000123456',
  source_id: 'secop',
  source_url: 'https://www.datos.gov.co/d/jbjy-vk9h',
  publisher: 'Colombia Compra Eficiente',
  outcome: 'not_screened',
  run_id: null,
  run_status: null,
  last_attempted_at: null,
  last_successful_at: null,
  source_updated_at: null,
  cache_age_seconds: null,
  cache_ttl_seconds: 86400,
  warnings: ['Participar en contratación pública no constituye una señal adversa.'],
  error_code: null,
  summary: null,
}
const contract: Contract = {
  contract_id: 'CONTRACT-1',
  process_id: 'PROCESS-1',
  reference: 'REF',
  original_supplier_identifier: '000123456',
  normalized_supplier_identifier: '000123456',
  supplier_document_type: 'NIT',
  source_identifier: 'row1',
  match_method: 'exact_supplier_nit',
  match_status: 'verified',
  buyer: 'SYNTHETIC BUYER',
  buyer_nit: '899999999',
  description: 'SYNTHETIC SERVICES',
  value: '999999999999999999.12',
  currency: 'COP',
  currency_basis: 'application_policy',
  raw_status: 'En ejecución',
  status: 'in_execution',
  contract_type: 'Servicios',
  modality: 'Directa',
  signature_date: '2025-01-01',
  start_date: null,
  end_date: null,
  department: null,
  city: null,
  source_url: 'https://www.datos.gov.co/d/jbjy-vk9h',
  source_link_label: 'Conjunto de datos oficial',
  retrieved_at: '2026-11-18T12:00:00Z',
  source_updated_at: null,
  evidence_id: 'evidence',
}
const completed: SecopScreening = {
  ...initial,
  run_id: 'run',
  outcome: 'completed_with_matches',
  run_status: 'completed',
  last_attempted_at: '2026-11-18T12:00:00Z',
  last_successful_at: '2026-11-18T12:00:00Z',
  cache_age_seconds: 10,
  summary: {
    total_contracts: 12,
    total_values: { COP: '999999999999999999.12' },
    monetary_contracts: 12,
    missing_or_invalid_values: 0,
    unknown_currency_contracts: 0,
    zero_value_contracts: 0,
    distinct_buyers: 1,
    latest_signature_date: '2025-01-01',
    annual: [{ label: '2025', count: 12, values: { COP: '999999999999999999.12' } }],
    statuses: [{ label: 'En ejecución', count: 12, values: { COP: '999999999999999999.12' } }],
    top_buyers: [{ label: 'SYNTHETIC BUYER', count: 12, values: { COP: '999999999999999999.12' } }],
    modalities: [{ label: 'Directa', count: 12, values: { COP: '999999999999999999.12' } }],
    departments: [],
    executive_summary: 'Se identificaron 12 contratos únicos verificados.',
  },
}
function show(data = initial, items = [contract], total = 12) {
  vi.mocked(api.secop).mockResolvedValue(data)
  vi.mocked(api.secopContracts).mockResolvedValue({
    items,
    total,
    page: 1,
    page_size: 5,
    has_more: items.length < total,
    run_id: 'run',
  })
  vi.mocked(api.secopContract).mockResolvedValue(contract)
  render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
        })
      }
    >
      <Screening companyId="company" />
    </QueryClientProvider>,
  )
}
beforeEach(() => vi.resetAllMocks())

test('initial state does not fabricate KPI zeros or call refresh', async () => {
  show()
  expect(await screen.findByRole('button', { name: 'Consultar SECOP' })).toBeEnabled()
  expect(screen.queryByRole('heading', { name: 'Total contratos' })).not.toBeInTheDocument()
  expect(api.refreshSecop).not.toHaveBeenCalled()
})
test('refresh calls real API workflow and renders verified metrics and official links', async () => {
  vi.mocked(api.refreshSecop).mockResolvedValue(completed)
  show()
  await userEvent.click(await screen.findByRole('button', { name: 'Consultar SECOP' }))
  expect(
    await screen.findByRole('complementary', { name: 'Resumen de la consulta SECOP' }),
  ).toHaveTextContent(/Total contratos\s*12/)
  expect(api.refreshSecop).toHaveBeenCalledWith('company')
  expect(screen.getByRole('meter', { name: '2025: 999999999999999999.12 COP' })).toBeInTheDocument()
  expect(screen.getAllByText('999.999.999.999.999.999,12 COP').length).toBeGreaterThan(0)
  expect(screen.getAllByRole('link', { name: 'Conjunto de datos oficial ↗' })[0]).toHaveAttribute(
    'href',
    initial.source_url,
  )
  expect(
    screen.getByRole('heading', { name: 'Valor contractual total' }).parentElement,
  ).toHaveTextContent('999.999.999.999.999.999,12 COP')
})
test('loading refresh disables duplicate clicks', async () => {
  vi.mocked(api.refreshSecop).mockReturnValue(new Promise(() => {}))
  show()
  const button = await screen.findByRole('button', { name: 'Consultar SECOP' })
  await userEvent.click(button)
  expect(button).toBeDisabled()
  expect(screen.getByRole('status')).toHaveTextContent('Consultando SECOP II')
})
test('refresh error does not become empty result', async () => {
  vi.mocked(api.refreshSecop).mockRejectedValue(new Error('SECOP unavailable'))
  show()
  await userEvent.click(await screen.findByRole('button', { name: 'Consultar SECOP' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('SECOP unavailable')
  expect(screen.queryByRole('heading', { name: 'Total contratos' })).not.toBeInTheDocument()
})
test('pagination and detail preserve screening snapshot and source evidence', async () => {
  show(completed)
  await userEvent.click(await screen.findByRole('button', { name: 'Siguiente →' }))
  await waitFor(() =>
    expect(api.secopContracts).toHaveBeenLastCalledWith(
      'company',
      expect.any(URLSearchParams),
      expect.any(AbortSignal),
    ),
  )
  const params = vi.mocked(api.secopContracts).mock.calls.at(-1)![1]
  expect(params.get('page')).toBe('2')
  expect(params.get('page_size')).toBe('5')
  expect(params.get('run_id')).toBe('run')
  await userEvent.click(await screen.findByRole('button', { name: 'CONTRACT-1' }))
  expect(
    await screen.findByRole('heading', { name: 'Detalle del contrato CONTRACT-1' }),
  ).toBeInTheDocument()
  expect(await screen.findByText('exact_supplier_nit / verified')).toBeInTheDocument()
  expect(api.secopContract).toHaveBeenCalledWith(
    'company',
    'CONTRACT-1',
    expect.any(AbortSignal),
    'run',
  )
  await userEvent.click(screen.getByRole('button', { name: 'Cerrar detalle' }))
  expect(screen.queryByRole('region', { name: 'Detalle del contrato' })).not.toBeInTheDocument()
})
test('stale successful results remain visible with warning', async () => {
  show({ ...completed, outcome: 'stale', error_code: 'source_timeout' })
  await waitFor(() =>
    expect(
      screen.getAllByRole('status').some((el) => el.textContent?.includes('Datos anteriores')),
    ).toBe(true),
  )
  expect(
    screen.getByRole('complementary', { name: 'Resumen de la consulta SECOP' }),
  ).toHaveTextContent(/Total contratos\s*12/)
})
test('missing NIT disables screening', async () => {
  show({ ...initial, nit: null, outcome: 'missing_nit' })
  expect(await screen.findByRole('button', { name: 'Consultar SECOP' })).toBeDisabled()
})
test('completed zero matches states dataset scope', async () => {
  vi.mocked(api.secopContracts).mockResolvedValue({
    items: [],
    total: 0,
    page: 1,
    page_size: 5,
    has_more: false,
    run_id: 'run',
  })
  show({
    ...completed,
    outcome: 'completed_no_matches',
    summary: {
      ...completed.summary!,
      total_contracts: 0,
      total_values: { COP: '0' },
      monetary_contracts: 0,
      executive_summary: 'Se identificaron 0 contratos únicos.',
      annual: [],
      statuses: [],
      top_buyers: [],
      modalities: [],
    },
  })
  expect(
    await screen.findByText(/Esto no significa que la empresa nunca haya contratado con el Estado/),
  ).toBeInTheDocument()
})
test('upstream unavailable is distinct from no matches', async () => {
  show({ ...initial, outcome: 'source_unavailable' })
  expect(await screen.findByText(/No se pudo comprobar/)).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Total contratos' })).not.toBeInTheDocument()
})

test('portfolio above 5000 shows explicit alert without false zero-match metrics', async () => {
  show({ ...initial, outcome: 'failed', error_code: 'secop_limit_exceeded' })
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('La consulta supera el límite de 5.000 registros')
  expect(alert).toHaveTextContent('no se presentan totales parciales')
  expect(alert).toHaveTextContent('Esto no significa ausencia de contratos')
  expect(screen.queryByRole('heading', { name: 'Total contratos' })).not.toBeInTheDocument()
})

test('portfolio cap alert identifies retained previous successful results', async () => {
  show({ ...completed, outcome: 'stale', error_code: 'secop_limit_exceeded' })
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('Se conservan los resultados de la última consulta exitosa')
  expect(
    await screen.findByRole('complementary', { name: 'Resumen de la consulta SECOP' }),
  ).toHaveTextContent(/Total contratos\s*12/)
})

test('summary contains four metric cards and no synthesized paragraph', async () => {
  show(completed)
  const summary = await screen.findByRole('complementary', { name: 'Resumen de la consulta SECOP' })
  expect(within(summary).getAllByRole('article')).toHaveLength(4)
  for (const title of [
    'Total contratos',
    'Valor contractual total',
    'Entidades contratantes',
    'Firma más reciente',
  ]) {
    expect(within(summary).getByRole('heading', { name: title, level: 4 })).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { name: title })).toHaveLength(1)
  }
  expect(summary).not.toHaveTextContent('Se identificaron')
  expect(within(summary).getByText('999.999.999.999.999.999,12 COP')).toBeInTheDocument()
  expect(
    screen.queryByRole('heading', { name: 'Actividad anual por fecha de firma' }),
  ).not.toBeInTheDocument()
})

test('sort direction button toggles direction and resets pagination', async () => {
  show(completed)
  await userEvent.click(await screen.findByRole('button', { name: 'Siguiente →' }))
  const toggle = await screen.findByRole('button', {
    name: 'Orden descendente. Cambiar a ascendente',
  })
  expect(toggle).toHaveTextContent('↓')
  await userEvent.click(toggle)
  await screen.findByRole('button', { name: 'Orden ascendente. Cambiar a descendente' })
  await waitFor(() => {
    const params = vi.mocked(api.secopContracts).mock.calls.at(-1)![1]
    expect(params.get('direction')).toBe('asc')
    expect(params.get('page')).toBe('1')
    expect(params.get('page_size')).toBe('5')
  })
  expect(screen.queryByLabelText('Dirección')).not.toBeInTheDocument()
  await userEvent.selectOptions(screen.getByLabelText('Ordenar por'), 'value')
  await waitFor(() =>
    expect(vi.mocked(api.secopContracts).mock.calls.at(-1)![1].get('sort')).toBe('value'),
  )
})

test('contract pagination displays the same range structure as Capital Markets', async () => {
  const items = Array.from({ length: 5 }, (_, i) => ({
    ...contract,
    contract_id: `CONTRACT-${i + 1}`,
  }))
  show(completed, items, 7)
  const pagination = await screen.findByRole('navigation', { name: 'Páginas de contratos' })
  expect(pagination).toHaveTextContent('1 - 5 de 7')
  expect(screen.getByText('7 contratos encontrados')).toBeInTheDocument()
  expect(within(pagination).getByRole('button', { name: '← Anterior' })).toBeDisabled()
  vi.mocked(api.secopContracts).mockResolvedValue({
    items: items.slice(0, 2),
    page: 2,
    page_size: 5,
    total: 7,
    has_more: false,
    run_id: 'run',
  })
  await userEvent.click(within(pagination).getByRole('button', { name: 'Siguiente →' }))
  const lastPage = await screen.findByRole('navigation', { name: 'Páginas de contratos' })
  expect(lastPage).toHaveTextContent('6 - 7 de 7')
  expect(within(lastPage).getByRole('button', { name: 'Siguiente →' })).toBeDisabled()
})

test('status chart displays all source statuses and filters by the exact reported status', async () => {
  const names = ['Aprobado', 'En aprobación', 'Enviado proveedor', 'Estado nuevo']
  show(
    {
      ...completed,
      summary: {
        ...completed.summary!,
        statuses: names.map((label) => ({ label, count: 1, values: {} })),
        top_buyers: [{ label: 'Entidad Mixta', count: 1, values: {} }],
        modalities: [{ label: 'Contratación directa', count: 1, values: {} }],
      },
    },
    [{ ...contract, buyer: 'Entidad Mixta', modality: 'Contratación directa' }],
  )
  await screen.findByRole('heading', { name: 'Contratos por estado' })
  for (const name of names) {
    expect(
      screen.getByRole('meter', { name: `${name.toLocaleUpperCase('es-CO')}: 1 contratos` }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('option', { name: name.toLocaleUpperCase('es-CO') }),
    ).toBeInTheDocument()
  }
  expect(screen.queryByText('Otro / no informado')).not.toBeInTheDocument()
  expect(await screen.findByRole('cell', { name: 'ENTIDAD MIXTA' })).toBeInTheDocument()
  expect(screen.getByRole('cell', { name: 'CONTRATACIÓN DIRECTA' })).toBeInTheDocument()
  expect(screen.getByRole('option', { name: 'CONTRATACIÓN DIRECTA' })).toHaveValue(
    'Contratación directa',
  )
  await userEvent.selectOptions(screen.getByLabelText('Estado'), 'En aprobación')
  await waitFor(() => {
    const params = vi.mocked(api.secopContracts).mock.calls.at(-1)![1]
    expect(params.get('raw_status')).toBe('En aprobación')
    expect(params.has('status')).toBe(false)
  })
  await userEvent.selectOptions(screen.getByLabelText('Modalidad'), 'Contratación directa')
  await userEvent.type(screen.getByLabelText('Entidad (nombre exacto)'), 'ENTIDAD MIXTA')
  await waitFor(() => {
    const params = vi.mocked(api.secopContracts).mock.calls.at(-1)![1]
    expect(params.get('modality')).toBe('Contratación directa')
    expect(params.get('entity')).toBe('Entidad Mixta')
  })
})
