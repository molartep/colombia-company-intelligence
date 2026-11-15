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
      details_availability: 'available',
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

test('RNVE description, contacts, administration and collapsed provenance', async () => {
  setup({
    ...profile,
    issuers: [
      {
        ...profile.issuers[0]!,
        regulator_entity_type_description: 'SYNTHETIC ENTITY TYPE',
        contacts: {
          institutional_email: 'registry@example.test',
          address: null,
          city: null,
          phone: null,
          website: 'www.example.test',
          social_networks: [],
        },
        administration: {
          board_members_count: 0,
          legal_representative: 'SYNTHETIC REPRESENTATIVE',
          rnve_information_representative: null,
        },
      },
    ],
  })
  await screen.findByText('001 — SYNTHETIC ENTITY TYPE')
  expect(screen.getByText('registry@example.test')).toBeVisible()
  expect(screen.getByRole('link', { name: 'www.example.test ↗' })).toHaveAttribute(
    'href',
    'https://www.example.test/',
  )
  const administration = screen.getByRole('heading', { name: 'Administración' }).closest('article')!
  expect(within(administration).getByText('0')).toBeVisible()
  expect(within(administration).getByText('Missing')).toHaveClass('value-pill--missing')
  expect(screen.queryByText(/Propiedad: no evaluada/)).not.toBeInTheDocument()
  const summary = screen.getByText('Fuentes y verificación')
  expect(summary.closest('details')).not.toHaveAttribute('open')
  await userEvent.click(summary)
  expect(summary.closest('details')).toHaveAttribute('open')
})

test('missing contact and administration values use red Missing pills', async () => {
  setup()
  await screen.findByRole('heading', { name: 'Administración' })
  for (const heading of ['Datos de contacto', 'Administración']) {
    const panel = screen.getByRole('heading', { name: heading }).closest('article')!
    const missing = within(panel).getAllByText('Missing')
    expect(missing).toHaveLength(heading === 'Administración' ? 3 : 6)
    missing.forEach((pill) => expect(pill).toHaveClass('value-pill--missing'))
  }
})

test('candidate contacts are not attributed', async () => {
  setup({
    ...profile,
    rnve: { status: 'unknown', match_status: 'potential' },
    issuers: [
      {
        ...profile.issuers[0]!,
        match_status: 'potential',
        contacts: {
          institutional_email: 'candidate@example.test',
          address: null,
          city: null,
          phone: null,
          website: null,
          social_networks: [],
        },
      },
    ],
  })
  await screen.findByRole('heading', { name: 'Datos de contacto' })
  expect(screen.queryByText('candidate@example.test')).not.toBeInTheDocument()
})

test.each(['javascript:alert(1)', 'https://https://www.example.test'])(
  'unsafe RNVE website %s does not become a hyperlink',
  async (website) => {
    setup({
      ...profile,
      issuers: [
        {
          ...profile.issuers[0]!,
          contacts: {
            institutional_email: null,
            address: null,
            city: null,
            phone: null,
            website,
            social_networks: [],
          },
        },
      ],
    })
    await screen.findByText(website)
    expect(screen.queryByRole('link', { name: `${website} ↗` })).not.toBeInTheDocument()
  },
)

test('failed summary retrieval is unavailable rather than missing source evidence', async () => {
  setup({
    ...profile,
    issuers: [
      {
        ...profile.issuers[0]!,
        details_availability: 'failed_to_retrieve',
        details_last_attempt_failed: true,
      },
    ],
  })
  await screen.findByText(/No se pudo recuperar el resumen RNVE/)
  const panel = screen.getByRole('heading', { name: 'Administración' }).closest('article')!
  expect(within(panel).getAllByText('Unavailable')).toHaveLength(3)
  expect(within(panel).queryByText('Missing')).not.toBeInTheDocument()
})

test('unchecked administration is distinct from fields missing in a checked summary', async () => {
  setup({
    ...profile,
    issuers: [{ ...profile.issuers[0]!, details_availability: 'not_yet_checked' }],
  })
  await screen.findByRole('heading', { name: 'Administración' })
  const panel = screen.getByRole('heading', { name: 'Administración' }).closest('article')!
  expect(within(panel).getAllByText('Not yet checked')).toHaveLength(3)
  expect(within(panel).queryByText('Missing')).not.toBeInTheDocument()
})

test('failed refresh retains cached administration with an explicit stale notice', async () => {
  setup({
    ...profile,
    issuers: [
      {
        ...profile.issuers[0]!,
        details_availability: 'stale',
        details_last_attempt_failed: true,
        administration: {
          board_members_count: 7,
          legal_representative: 'SYNTHETIC CACHED REPRESENTATIVE',
          rnve_information_representative: null,
        },
      },
    ],
  })
  await screen.findByText('SYNTHETIC CACHED REPRESENTATIVE')
  expect(screen.getByText(/Se conservan los últimos datos recuperados/)).toBeVisible()
  const panel = screen.getByRole('heading', { name: 'Administración' }).closest('article')!
  expect(within(panel).getByText('7')).toBeVisible()
})

test('reopening Capital Markets refreshes a previously cached unchecked securities response', async () => {
  let fetched = false
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string) => ({
      ok: true,
      json: async () =>
        path.endsWith('/capital-markets')
          ? profile
          : fetched
            ? securities
            : { ...securities, items: [], has_more: false, availability: 'not_yet_checked' },
    })),
  )
  const element = (
    <QueryClientProvider client={client}>
      <CapitalMarkets companyId="synthetic" />
    </QueryClientProvider>
  )
  const first = render(element)
  await screen.findByText(/Valores aún no consultados/)
  first.unmount()
  fetched = true
  render(element)
  expect(await screen.findByText('BO SYNTHETIC BOND')).toBeVisible()
  expect(screen.queryByText(/Valores aún no consultados/)).not.toBeInTheDocument()
})

test('failed securities retrieval reports unavailability instead of checked absence', async () => {
  setup(profile, { ...securities, items: [], has_more: false, availability: 'failed_to_retrieve' })
  await screen.findByText(/Se reintentará al abrir Capital Markets después de 15 minutos/)
  expect(
    screen.getByText('No se presenta una conclusión negativa sobre instrumentos.'),
  ).toBeVisible()
  expect(screen.queryByText(/No hay instrumentos en el reporte consultado/)).not.toBeInTheDocument()
})
