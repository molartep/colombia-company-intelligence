import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { vi } from 'vitest'
import { Screening } from './components/Screening'
import { changeLanguage } from './i18n'
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
  expect(await screen.findByRole('button', { name: 'Query SECOP' })).toBeEnabled()
  expect(screen.queryByRole('heading', { name: 'Total contracts' })).not.toBeInTheDocument()
  expect(api.refreshSecop).not.toHaveBeenCalled()
})
test('refresh calls real API workflow and renders verified metrics and official links', async () => {
  vi.mocked(api.refreshSecop).mockResolvedValue(completed)
  show()
  await userEvent.click(await screen.findByRole('button', { name: 'Query SECOP' }))
  expect(
    await screen.findByRole('complementary', { name: 'SECOP query summary' }),
  ).toHaveTextContent(/Total contracts\s*12/)
  expect(api.refreshSecop).toHaveBeenCalledWith('company')
  expect(
    screen.getByRole('meter', { name: '2025: 999,999,999,999,999,999.12' }),
  ).toBeInTheDocument()
  expect(screen.getAllByText('999,999,999,999,999,999.12').length).toBeGreaterThan(0)
  expect(screen.getAllByRole('link', { name: 'Official dataset ↗' })[0]).toHaveAttribute(
    'href',
    initial.source_url,
  )
  expect(
    screen.getByRole('heading', { name: 'Total contract value (COP)' }).parentElement,
  ).toHaveTextContent('999,999,999,999,999,999.12')
})
test('loading refresh disables duplicate clicks', async () => {
  vi.mocked(api.refreshSecop).mockReturnValue(new Promise(() => {}))
  show()
  const button = await screen.findByRole('button', { name: 'Query SECOP' })
  await userEvent.click(button)
  expect(button).toBeDisabled()
  expect(screen.getByRole('status')).toHaveTextContent('Querying SECOP II')
})
test('refresh error does not become empty result', async () => {
  vi.mocked(api.refreshSecop).mockRejectedValue(new Error('SECOP unavailable'))
  show()
  await userEvent.click(await screen.findByRole('button', { name: 'Query SECOP' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'The request could not be completed. Please try again.',
  )
  expect(screen.queryByRole('heading', { name: 'Total contracts' })).not.toBeInTheDocument()
})
test('pagination and detail preserve screening snapshot and source evidence', async () => {
  show(completed)
  await userEvent.click(await screen.findByRole('button', { name: 'Next →' }))
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
    await screen.findByRole('heading', { name: 'Contract details CONTRACT-1' }),
  ).toBeInTheDocument()
  expect(await screen.findByText('Exact supplier NIT / Verified')).toBeInTheDocument()
  expect(api.secopContract).toHaveBeenCalledWith(
    'company',
    'CONTRACT-1',
    expect.any(AbortSignal),
    'run',
  )
  await userEvent.click(screen.getByRole('button', { name: 'Close details' }))
  expect(screen.queryByRole('region', { name: 'Contract details' })).not.toBeInTheDocument()
})
test('stale successful results remain visible with warning', async () => {
  show({ ...completed, outcome: 'stale', error_code: 'source_timeout' })
  await waitFor(() =>
    expect(
      screen.getAllByRole('status').some((el) => el.textContent?.includes('Previous data')),
    ).toBe(true),
  )
  expect(screen.getByRole('complementary', { name: 'SECOP query summary' })).toHaveTextContent(
    /Total contracts\s*12/,
  )
})
test('missing NIT disables screening', async () => {
  show({ ...initial, nit: null, outcome: 'missing_nit' })
  expect(await screen.findByRole('button', { name: 'Query SECOP' })).toBeDisabled()
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
    await screen.findByText(
      /This does not mean the company has never contracted with the government/,
    ),
  ).toBeInTheDocument()
})
test('upstream unavailable is distinct from no matches', async () => {
  show({ ...initial, outcome: 'source_unavailable' })
  expect(await screen.findByText(/Contract participation could not be checked/)).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Total contracts' })).not.toBeInTheDocument()
})

test('portfolio above 5000 shows explicit alert without false zero-match metrics', async () => {
  show({ ...initial, outcome: 'failed', error_code: 'secop_limit_exceeded' })
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('The query exceeds the 5,000-record limit')
  expect(alert).toHaveTextContent('no partial totals are presented')
  expect(alert).toHaveTextContent('This does not mean there are no contracts')
  expect(screen.queryByRole('heading', { name: 'Total contracts' })).not.toBeInTheDocument()
})

test('portfolio cap alert identifies retained previous successful results', async () => {
  show({ ...completed, outcome: 'stale', error_code: 'secop_limit_exceeded' })
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('Results from the last successful query are retained')
  expect(
    await screen.findByRole('complementary', { name: 'SECOP query summary' }),
  ).toHaveTextContent(/Total contracts\s*12/)
})

test('summary contains four metric cards and no synthesized paragraph', async () => {
  show(completed)
  const summary = await screen.findByRole('complementary', { name: 'SECOP query summary' })
  expect(within(summary).getAllByRole('article')).toHaveLength(4)
  for (const title of [
    'Total contracts',
    'Total contract value (COP)',
    'Contracting entities',
    'Most recent signature',
  ]) {
    expect(within(summary).getByRole('heading', { name: title, level: 4 })).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { name: title })).toHaveLength(1)
  }
  expect(summary).not.toHaveTextContent('Se identificaron')
  expect(within(summary).getByText('999,999,999,999,999,999.12')).toBeInTheDocument()
  expect(
    screen.queryByRole('heading', { name: 'Actividad anual por fecha de firma' }),
  ).not.toBeInTheDocument()
})

test('sort direction button toggles direction and resets pagination', async () => {
  show(completed)
  await userEvent.click(await screen.findByRole('button', { name: 'Next →' }))
  const toggle = await screen.findByRole('button', {
    name: 'Descending order. Switch to ascending',
  })
  expect(toggle).toHaveTextContent('↓')
  await userEvent.click(toggle)
  await screen.findByRole('button', { name: 'Ascending order. Switch to descending' })
  await waitFor(() => {
    const params = vi.mocked(api.secopContracts).mock.calls.at(-1)![1]
    expect(params.get('direction')).toBe('asc')
    expect(params.get('page')).toBe('1')
    expect(params.get('page_size')).toBe('5')
  })
  expect(screen.queryByLabelText('Address')).not.toBeInTheDocument()
  await userEvent.selectOptions(screen.getByLabelText('Sort by'), 'value')
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
  const pagination = await screen.findByRole('navigation', { name: 'Contract pages' })
  expect(pagination).toHaveTextContent('1 - 5 of 7')
  expect(screen.getByText('7 contracts found')).toBeInTheDocument()
  expect(within(pagination).getByRole('button', { name: '← Previous' })).toBeDisabled()
  vi.mocked(api.secopContracts).mockResolvedValue({
    items: items.slice(0, 2),
    page: 2,
    page_size: 5,
    total: 7,
    has_more: false,
    run_id: 'run',
  })
  await userEvent.click(within(pagination).getByRole('button', { name: 'Next →' }))
  const lastPage = await screen.findByRole('navigation', { name: 'Contract pages' })
  expect(lastPage).toHaveTextContent('6 - 7 of 7')
  expect(within(lastPage).getByRole('button', { name: 'Next →' })).toBeDisabled()
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
  await screen.findByRole('heading', { name: 'Contracts by status' })
  for (const name of names) {
    expect(
      screen.getByRole('meter', { name: `${name.toLocaleUpperCase('es-CO')}: 1 contract` }),
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
  await userEvent.selectOptions(screen.getByLabelText('Status'), 'En aprobación')
  await waitFor(() => {
    const params = vi.mocked(api.secopContracts).mock.calls.at(-1)![1]
    expect(params.get('raw_status')).toBe('En aprobación')
    expect(params.has('status')).toBe(false)
  })
  await userEvent.selectOptions(screen.getByLabelText('Procurement method'), 'Contratación directa')
  await userEvent.type(screen.getByLabelText('Entity (exact name)'), 'Entidad Mixta')
  await waitFor(() => {
    const params = vi.mocked(api.secopContracts).mock.calls.at(-1)![1]
    expect(params.get('modality')).toBe('Contratación directa')
    expect(params.get('entity')).toBe('Entidad Mixta')
  })
})

test('missing-signature-date option comes first and sends a missing-date filter', async () => {
  show(completed)
  const year = await screen.findByLabelText('Signature year')
  expect(within(year).getAllByRole('option')[0]).toHaveTextContent('No signature date')
  await userEvent.selectOptions(year, 'missing')
  await waitFor(() => {
    const params = vi.mocked(api.secopContracts).mock.calls.at(-1)![1]
    expect(params.get('missing_signature_date')).toBe('true')
    expect(params.has('year')).toBe(false)
  })
  await userEvent.selectOptions(year, '2025')
  await waitFor(() => {
    const params = vi.mocked(api.secopContracts).mock.calls.at(-1)![1]
    expect(params.get('year')).toBe('2025')
    expect(params.has('missing_signature_date')).toBe(false)
  })
  expect(screen.queryByText(/0 sin moneda/)).not.toBeInTheDocument()
  expect(screen.queryByText(/0 sin valor válido/)).not.toBeInTheDocument()
})

test('single-currency sections label COP once and keep exact amounts without repeated units', async () => {
  show(completed)
  const summary = await screen.findByRole('complementary', { name: 'SECOP query summary' })
  expect(
    within(summary).getByRole('heading', { name: 'Total contract value (COP)' }),
  ).toBeInTheDocument()
  expect(within(summary).getByText('999,999,999,999,999,999.12')).toBeInTheDocument()
  expect(summary.querySelectorAll('wbr')).toHaveLength(0)
  expect(summary.querySelectorAll('.fit-metric-value')).toHaveLength(4)
  const table = await screen.findByRole('region', { name: 'Verified contracts table' })
  expect(within(table).getByRole('columnheader', { name: 'Value (COP)' })).toBeInTheDocument()
  expect(
    within(table).getByRole('cell', { name: '999,999,999,999,999,999.12' }),
  ).toBeInTheDocument()
  expect(within(table).queryByText(/COP\s+999|999.*COP/)).not.toBeInTheDocument()
})

test('mixed currencies retain explicit codes instead of assuming a shared currency', async () => {
  show(
    {
      ...completed,
      summary: { ...completed.summary!, total_values: { COP: '10.120000', USD: '3.450000' } },
    },
    [contract, { ...contract, contract_id: 'USD-1', value: '3.450000', currency: 'USD' }],
  )
  const summary = await screen.findByRole('complementary', { name: 'SECOP query summary' })
  expect(within(summary).getByRole('heading', { name: 'Total contract value' })).toBeInTheDocument()
  expect(summary).toHaveTextContent('COP 10.120000 · USD 3.450000')
  const table = await screen.findByRole('region', { name: 'Verified contracts table' })
  expect(within(table).getByRole('columnheader', { name: 'Value' })).toBeInTheDocument()
  expect(within(table).getByRole('cell', { name: '3.450000 USD' })).toBeInTheDocument()
})

test('contract filter choices are alphabetic uppercase labels with original API values', async () => {
  const options = ['Zeta', 'Ábaco', 'Beta']
  const groups = options.map((label) => ({ label, count: 1, values: {} }))
  show({
    ...completed,
    summary: { ...completed.summary!, statuses: groups, modalities: groups, top_buyers: groups },
  })
  for (const label of ['Status', 'Procurement method']) {
    const select = await screen.findByLabelText(label)
    expect(
      within(select)
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual(['All', 'ÁBACO', 'BETA', 'ZETA'])
    await userEvent.selectOptions(select, 'Ábaco')
  }
  expect(
    [...document.querySelectorAll('#secop-buyers option')].map((o) => o.getAttribute('value')),
  ).toEqual(['ÁBACO', 'BETA', 'ZETA'])
  await userEvent.type(screen.getByLabelText('Entity (exact name)'), 'ÁBACO')
  await waitFor(() => {
    const params = vi.mocked(api.secopContracts).mock.calls.at(-1)![1]
    expect(params.get('raw_status')).toBe('Ábaco')
    expect(params.get('modality')).toBe('Ábaco')
    expect(params.get('entity')).toBe('Ábaco')
  })
})

test('Spanish contract copy uses totals and the requested top-five and disclaimer wording', async () => {
  await changeLanguage('es')
  show({ ...completed, summary: { ...completed.summary!, monetary_contracts: 123 } })
  expect(await screen.findByText(/123 contratos incluidos en los totales/)).toBeInTheDocument()
  expect(
    screen.getByRole('heading', { name: 'Top cinco entidades por valor contractual (COP)' }),
  ).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Valor contractual total (COP)' })).toBeInTheDocument()
  expect(
    screen.getByText('Valores contractuales reportados, no representan pagos ni ingresos.'),
  ).toBeInTheDocument()
})

test('changing a selected filter keeps controls and previous rows mounted while results update', async () => {
  show(completed)
  const status = await screen.findByLabelText('Status')
  await screen.findByRole('button', { name: 'CONTRACT-1' })
  let finish!: (value: Awaited<ReturnType<typeof api.secopContracts>>) => void
  vi.mocked(api.secopContracts).mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  await userEvent.selectOptions(status, 'En ejecución')
  expect(screen.getByLabelText('Status')).toBe(status)
  expect(screen.getByRole('button', { name: 'CONTRACT-1' })).toBeInTheDocument()
  expect(screen.getByRole('region', { name: 'Verified contracts table' })).toHaveAttribute(
    'aria-busy',
    'true',
  )
  expect(screen.getByText('Updating… Previous results shown.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Next →' })).toBeDisabled()
  finish({
    items: [{ ...contract, contract_id: 'UPDATED-1' }],
    total: 1,
    page: 1,
    page_size: 5,
    has_more: false,
    run_id: 'run',
  })
  await screen.findByRole('button', { name: 'UPDATED-1' })
  expect(screen.getByLabelText('Status')).toBe(status)
  expect(screen.queryByText('Updating… Previous results shown.')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'CONTRACT-1' })).not.toBeInTheDocument()
  await userEvent.selectOptions(status, '')
  await waitFor(() =>
    expect(vi.mocked(api.secopContracts).mock.calls.at(-1)![1].has('raw_status')).toBe(false),
  )
})
