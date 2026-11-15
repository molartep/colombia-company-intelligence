import { render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { vi } from 'vitest'
import { CapitalMarkets } from './components/CapitalMarkets'
import type { MarketsProfile, SecuritiesPage } from './types/capitalMarkets'

const profile: MarketsProfile = {
  company_id: 'synthetic',
  rnve: { status: 'registered_active', match_status: 'verified' },
  exchange_listing: {
    status: 'unknown',
    availability: 'requires_authorized_source',
    explanation: 'No se ha verificado una fuente BVC autorizada y reproducible.',
  },
  equity_listed: null,
  ownership: { type: 'unknown', verification_status: 'not_assessed' },
  summary:
    'La empresa figura como emisor vigente en la fuente RNVE consultada. Se identificaron valores de deuda registrados. No se ha verificado un listado vigente de acciones en la BVC.',
  issuers: [
    {
      id: 'synthetic-issuer',
      nit: '000123456',
      source_nit: '000123456-7',
      verification_digit: '7',
      issuer_name: 'SYNTHETIC ISSUER SAS',
      regulator_entity_code: '001',
      regulator_entity_type: '001',
      registration_status: 'registered_active',
      last_verified_at: '2026-11-14T15:00:00Z',
      source_url: 'https://www.superfinanciera.gov.co/SIMEV2/rnve/emisoresinscritosvigentes',
      match_status: 'verified',
      snapshot_id: 'synthetic-snapshot',
    },
  ],
  instruments: [],
  securities_availability: 'available',
  sources: [],
  stale: false,
  limitations: [],
}
const securities: SecuritiesPage = {
  items: [
    {
      id: 'synthetic-bond',
      security_name: 'BO SYNTHETIC BOND',
      security_type_raw: 'BO',
      security_category: 'corporate_bonds',
      ticker: null,
      isin: null,
      ann_code: 'CO1234567890',
      issuance_number: '001',
      exchange: 'BVC',
      rnve_registration_date: '2024-02-29',
      bvc_registration_date: '2024-03-01',
      listing_status: 'unknown',
      authorized_amount: '1000000.5000',
      currency: 'COP',
      credit_rating: null,
      source_url: 'https://www.superfinanciera.gov.co/official-report',
      last_verified_at: '2026-11-14T15:00:00Z',
      stale: false,
      source_values: { 'Código ANN': 'CO1234567890' },
      snapshot_id: 'synthetic-snapshot',
    },
  ],
  page: 1,
  page_size: 20,
  has_more: true,
  availability: 'available',
}
function setup(data = profile, instruments = securities, failed = false) {
  const requests: URL[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string) => {
      const url = new URL(path, 'http://test')
      requests.push(url)
      return {
        ok: !failed,
        status: failed ? 503 : 200,
        json: async () =>
          failed
            ? { error: { message: 'Capital markets data unavailable.' } }
            : url.pathname.endsWith('/capital-markets')
              ? data
              : instruments,
      }
    }),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <CapitalMarkets companyId="synthetic" />
    </QueryClientProvider>,
  )
  return requests
}
afterEach(() => vi.unstubAllGlobals())

test('registered debt and SFC BVC dates do not imply listed shares or invented ISINs', async () => {
  setup()
  await screen.findByText('BO SYNTHETIC BOND')
  expect(screen.getByText('Inscrito en RNVE')).toBeVisible()
  const bvc = screen
    .getByRole('heading', { name: 'Bolsa de Valores de Colombia' })
    .closest('article')!
  expect(within(bvc).getByText('No verificado')).toBeVisible()
  expect(screen.getByText('ANN: CO1234567890')).toBeVisible()
  expect(screen.queryByText('ISIN: CO1234567890')).not.toBeInTheDocument()
  expect(screen.getByText('Ticker no informado')).toBeVisible()
  expect(screen.getByText('COP 1000000.5000')).toBeVisible()
  expect(screen.getByRole('link', { name: 'SFC ↗' })).toHaveAttribute(
    'href',
    securities.items[0]!.source_url,
  )
})

test('incomplete or missing evidence stays unknown and potential matches do not attribute instruments', async () => {
  const requests = setup({
    ...profile,
    rnve: { status: 'unknown', match_status: 'potential' },
    summary:
      'Se identificó una posible coincidencia con un emisor, pendiente de verificación de identidad.',
    issuers: [{ ...profile.issuers[0]!, match_status: 'potential' }],
  })
  await screen.findByText('Registro no determinado')
  expect(screen.getByText(/Los instrumentos del candidato no se atribuyen/)).toBeVisible()
  expect(requests).toHaveLength(1)
  expect(screen.queryByText('BO SYNTHETIC BOND')).not.toBeInTheDocument()
})

test('checked absence is qualified and does not claim never registered', async () => {
  setup({
    ...profile,
    rnve: { status: 'not_found_in_checked_source', match_status: 'unresolved' },
    issuers: [],
    summary:
      'La empresa no fue encontrada en el directorio vigente RNVE. Esto no descarta registros históricos.',
  })
  await screen.findByText('Sin coincidencia en la fuente consultada')
  expect(screen.getByText(/Esto no descarta registros históricos/)).toBeVisible()
  expect(screen.queryByText('BO SYNTHETIC BOND')).not.toBeInTheDocument()
})

test('stale evidence is distinct from source failure and absence', async () => {
  setup(
    { ...profile, stale: true },
    { ...securities, availability: 'stale', items: [{ ...securities.items[0]!, stale: true }] },
  )
  await screen.findByText('BO SYNTHETIC BOND')
  expect(screen.getByText(/Evidencia desactualizada o última actualización fallida/)).toBeVisible()
  expect(screen.getByText('Observación anterior')).toBeVisible()
  expect(screen.getByText(/Su vigencia requiere actualización/)).toBeVisible()
})

test('securities filters use API parameters and reset pagination', async () => {
  const requests = setup()
  await screen.findByText('BO SYNTHETIC BOND')
  await userEvent.click(screen.getByRole('button', { name: /Siguiente/ }))
  await waitFor(() => expect(requests.at(-1)!.searchParams.get('page')).toBe('2'))
  await userEvent.selectOptions(screen.getByLabelText('Categoría'), 'corporate_bonds')
  await waitFor(() => expect(requests.at(-1)!.searchParams.get('page')).toBe('1'))
  expect(requests.at(-1)!.searchParams.get('security_category')).toBe('corporate_bonds')
  await userEvent.selectOptions(screen.getByLabelText('Mercado registrado'), 'BVC')
  await waitFor(() => expect(requests.at(-1)!.searchParams.get('exchange')).toBe('BVC'))
  await userEvent.selectOptions(screen.getByLabelText('Estado de listado'), 'unknown')
  await waitFor(() => expect(requests.at(-1)!.searchParams.get('listing_status')).toBe('unknown'))
})

test('API errors remain errors instead of negative regulatory findings', async () => {
  setup(profile, securities, true)
  expect(await screen.findByRole('alert')).toHaveTextContent('Capital markets data unavailable.')
  expect(screen.queryByText('Sin coincidencia en la fuente consultada')).not.toBeInTheDocument()
})
