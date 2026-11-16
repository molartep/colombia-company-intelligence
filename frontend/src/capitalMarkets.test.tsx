import { render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { vi } from 'vitest'
import { CapitalMarkets } from './components/CapitalMarkets'
import type { MarketsProfile, SecuritiesPage } from './types/capitalMarkets'

const reportSource = {
  id: 'sfc_rnve_securities',
  name: 'SYNTHETIC SFC SECURITIES',
  institution: 'SFC',
  source_url: 'https://www.superfinanciera.gov.co/official-report',
  availability: 'available',
  last_ingestion_status: 'success',
  last_error: null as string | null,
  last_attempt_at: '2026-11-14T15:00:00Z',
  last_success_at: '2026-11-14T15:00:00Z',
  stale: false,
  latest_snapshot: {
    id: 'synthetic-snapshot',
    retrieved_at: '2026-11-14T15:00:00Z',
    published_at: null,
    observed_at: '2026-11-13T15:00:00Z',
    complete_current: false,
    content_hash: 'synthetic-hash',
  },
}
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
  sources: [reportSource],
  stale: false,
  limitations: [],
}
const securities: SecuritiesPage = {
  total: 11,
  unfiltered_total: 11,
  items: [
    {
      id: 'synthetic-bond',
      security_name: 'BO SYNTHETIC BOND',
      security_type_raw: 'BO',
      security_category: 'corporate_bonds',
      ticker: null,
      isin: null,
      ann_code: 'CO1234567890',
      issuance_number: '198705',
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
  page_size: 10,
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

async function openSecurities() {
  await userEvent.click(await screen.findByRole('heading', { name: /^Valores registrados/ }))
}

async function openAlerts() {
  await userEvent.click(await screen.findByText(/^Alertas \(/))
}

test('registered debt and SFC BVC dates do not imply listed shares or invented ISINs', async () => {
  setup()
  expect(
    (await screen.findByRole('heading', { name: /^Valores registrados/ })).closest('details'),
  ).not.toHaveAttribute('open')
  await openSecurities()
  await screen.findByText('BO SYNTHETIC BOND')
  expect(screen.getByText('Inscrito en RNVE')).toBeVisible()
  const bvc = screen
    .getByRole('heading', { name: 'Bolsa de Valores de Colombia' })
    .closest('article')!
  expect(within(bvc).getByText('Listado no verificado')).toBeVisible()
  expect(screen.getByText('ANN: CO1234567890')).toBeVisible()
  expect(screen.getByText('Emisión: May, 1987')).toBeVisible()
  for (const name of ['Estado', 'Importe', 'Calificación reportada'])
    expect(screen.getByRole('columnheader', { name })).toBeVisible()
  expect(
    screen.queryByText(
      'Instrumentos de la fuente SFC consultada. Su registro no verifica negociación vigente.',
    ),
  ).not.toBeInTheDocument()
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
  await openAlerts()
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
  expect(screen.queryByLabelText('Resumen de evidencia')).not.toBeInTheDocument()
  expect(screen.queryByText('BO SYNTHETIC BOND')).not.toBeInTheDocument()
})

test('stale evidence is distinct from source failure and absence', async () => {
  setup(
    { ...profile, stale: true, sources: [{ ...reportSource, stale: true }] },
    { ...securities, availability: 'stale', items: [{ ...securities.items[0]!, stale: true }] },
  )
  await openSecurities()
  await screen.findByText('BO SYNTHETIC BOND')
  await openAlerts()
  expect(screen.getByText(/Los datos de esta fuente superan/)).toBeVisible()
  expect(screen.getByText('Observación anterior')).toBeVisible()
  expect(screen.getByText('Observación anterior')).toBeVisible()
})

test('securities filters use API parameters and reset pagination', async () => {
  const requests = setup()
  await openSecurities()
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
  const summary = screen.getByText('Data Source Information')
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
  await openAlerts()
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
  await openSecurities()
  expect(await screen.findByText('BO SYNTHETIC BOND')).toBeVisible()
  expect(screen.queryByText(/Valores aún no consultados/)).not.toBeInTheDocument()
})

test('failed securities retrieval reports unavailability instead of checked absence', async () => {
  setup(profile, { ...securities, items: [], has_more: false, availability: 'failed_to_retrieve' })
  await openSecurities()
  await screen.findByText(/Se reintentará al abrir Capital Markets después de 15 minutos/)
  expect(
    screen.getByText('No se presenta una conclusión negativa sobre instrumentos.'),
  ).toBeVisible()
  expect(screen.queryByText(/No hay instrumentos en el reporte consultado/)).not.toBeInTheDocument()
})

test('top alerts navigate to source controls; each control refreshes only its source', async () => {
  const paths: string[] = []
  let complete: (() => void) | undefined
  const held = new Promise<void>((resolve) => {
    complete = resolve
  })
  let refreshed = false
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string) => {
      paths.push(path)
      if (path.includes('refresh=true')) {
        await held
        refreshed = true
      }
      return {
        ok: true,
        json: async () =>
          new URL(path, 'http://test').pathname.endsWith('/capital-markets')
            ? { ...profile, stale: !refreshed, sources: [{ ...reportSource, stale: !refreshed }] }
            : {
                ...securities,
                items: [
                  {
                    ...securities.items[0]!,
                    security_name: refreshed ? 'SYNTHETIC NEW BOND' : 'SYNTHETIC OLD BOND',
                  },
                ],
              },
      }
    }),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <CapitalMarkets companyId="synthetic" />
    </QueryClientProvider>,
  )
  await openSecurities()
  await screen.findByText('SYNTHETIC OLD BOND')
  await openAlerts()
  const alert = screen
    .getByText(/Los datos de esta fuente superan/)
    .closest<HTMLElement>('.refresh-alert')!
  expect(within(alert).getByText(reportSource.name)).toBeVisible()
  expect(within(alert).getByText('Última recuperación exitosa')).toBeVisible()
  await userEvent.click(within(alert).getByRole('button', { name: 'Refresh data' }))
  const card = screen.getByRole('heading', { name: 'Data Source Information' }).closest('details')!
  expect(card).toHaveAttribute('open')
  expect(paths.some((p) => p.includes('refresh=true'))).toBe(false)
  const sourceButton = within(card).getByRole('button', { name: `Refresh ${reportSource.name}` })
  await userEvent.click(sourceButton)
  expect(sourceButton).toBeDisabled()
  complete!()
  await screen.findByText('SYNTHETIC NEW BOND')
  expect(paths.filter((p) => p.includes('refresh=true'))).toEqual([
    '/api/v1/companies/synthetic/capital-markets?refresh=true&refresh_source=sfc_rnve_securities',
  ])
})

test('both source cards stay collapsed initially and errors name the affected source', async () => {
  setup({
    ...profile,
    sources: [
      {
        ...reportSource,
        stale: true,
        last_ingestion_status: 'failed',
        last_error: 'capital_source_timeout',
      },
    ],
  })
  const title = await screen.findByRole('heading', { name: 'Data Source Information' })
  const card = title.closest('details')!
  expect(card).not.toHaveAttribute('open')
  expect(screen.getByText(/^Alertas \(/).closest('details')).not.toHaveAttribute('open')
  await openAlerts()
  const alert = screen
    .getByText(/La última actualización falló/)
    .closest<HTMLElement>('.refresh-alert')!
  expect(within(alert).getByText(reportSource.name)).toBeVisible()
  expect(within(alert).getByText('capital_source_timeout')).toBeVisible()
  expect(within(alert).getByText('Último intento')).toBeVisible()
})

test('failed source refresh retains instruments and displays the request error by that source', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string) => ({
      ok: !path.includes('refresh=true'),
      status: path.includes('refresh=true') ? 503 : 200,
      json: async () =>
        path.includes('refresh=true')
          ? { error: { message: 'SYNTHETIC refresh unavailable' } }
          : new URL(path, 'http://test').pathname.endsWith('/capital-markets')
            ? profile
            : securities,
    })),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <CapitalMarkets companyId="synthetic" />
    </QueryClientProvider>,
  )
  await openSecurities()
  await screen.findByText('BO SYNTHETIC BOND')
  await userEvent.click(screen.getByRole('heading', { name: 'Data Source Information' }))
  const provider = screen.getByRole('region', { name: reportSource.name })
  await userEvent.click(
    within(provider).getByRole('button', { name: `Refresh ${reportSource.name}` }),
  )
  expect(await within(provider).findByText(/SYNTHETIC refresh unavailable/)).toBeVisible()
  expect(screen.getByText('BO SYNTHETIC BOND')).toBeVisible()
})

test('10-record pages show filtered totals, ranges and a stable overall heading count', async () => {
  const requests: URL[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string) => {
      const url = new URL(path, 'http://test')
      requests.push(url)
      const filtered = url.searchParams.has('security_category')
      const page = Number(url.searchParams.get('page') || 1)
      const total = filtered ? 1 : 12
      const offset = (page - 1) * 10
      const items = Array.from(
        { length: Math.min(10, Math.max(0, total - offset)) },
        (_, index) => ({
          ...securities.items[0]!,
          id: `synthetic-${offset + index}`,
          security_name: `SYNTHETIC BOND ${offset + index}`,
        }),
      )
      return {
        ok: true,
        json: async () =>
          url.pathname.endsWith('/capital-markets')
            ? profile
            : {
                ...securities,
                items,
                page,
                page_size: 10,
                total,
                unfiltered_total: 12,
                has_more: offset + items.length < total,
              },
      }
    }),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <CapitalMarkets companyId="synthetic" />
    </QueryClientProvider>,
  )
  await openSecurities()
  await screen.findByText('1 - 10 de 12')
  expect(screen.getByRole('heading', { name: 'Valores registrados (12)' })).toBeVisible()
  expect(screen.getByText('12 records found')).toBeVisible()
  expect(screen.getAllByRole('row')).toHaveLength(11)
  expect(requests.at(-1)!.searchParams.get('page_size')).toBe('10')
  await userEvent.click(screen.getByRole('button', { name: /Siguiente/ }))
  await screen.findByText('11 - 12 de 12')
  expect(screen.getAllByRole('row')).toHaveLength(3)
  await userEvent.selectOptions(screen.getByLabelText('Categoría'), 'corporate_bonds')
  await screen.findByText('1 - 1 de 1')
  expect(screen.getByText('1 record found')).toBeVisible()
  expect(screen.getByRole('heading', { name: 'Valores registrados (12)' })).toBeVisible()
  expect(requests.at(-1)!.searchParams.get('page')).toBe('1')
})

test('BVC displays only returned exact-code price/ticker observations and provenance', async () => {
  setup({
    ...profile,
    equity_listed: true,
    exchange_listing: {
      status: 'verified_listed',
      availability: 'available',
      explanation: 'SYNTHETIC exact-code BVC match.',
      quotes: [
        {
          instrument_id: 'synthetic-common',
          superfinanciera_code: 'COSYNTH00001',
          ticker: 'SYNTHETIC',
          last_price: '1234.50',
          raw_price: '1,234.50',
          currency: null,
          isin: 'CO0000000001',
          reported_state: 'Activo',
          retrieved_at: '2026-11-15T12:00:00Z',
          price_as_of: null,
          source_url: 'https://www.bvc.com.co/renta-variable-mercado-local/synthetic',
          stale: false,
        },
      ],
    },
  })
  await screen.findByText('SYNTHETIC')
  const panel = screen
    .getByRole('heading', { name: 'Bolsa de Valores de Colombia' })
    .closest('article')!
  expect(within(panel).getByText('1.234,5')).toBeVisible()
  expect(within(panel).getByText('COSYNTH00001')).toBeVisible()
  expect(
    within(panel).getByRole('link', { name: 'Fuente: Bolsa de Valores de Colombia ↗' }),
  ).toHaveAttribute('href', 'https://www.bvc.com.co/renta-variable-mercado-local/synthetic')
  expect(within(panel).getByText('No informada')).toBeVisible()
})

test('blocked BVC page leaves price and ticker explicitly unverified', async () => {
  setup({
    ...profile,
    exchange_listing: {
      status: 'unknown',
      availability: 'failed_to_retrieve',
      explanation: 'SYNTHETIC BVC HTTP 403; no negative finding.',
      quotes: [],
    },
  })
  await screen.findByRole('heading', { name: 'Bolsa de Valores de Colombia' })
  const panel = screen
    .getByRole('heading', { name: 'Bolsa de Valores de Colombia' })
    .closest('article')!
  expect(within(panel).queryByText('2,560.00')).not.toBeInTheDocument()
  expect(within(panel).getByText('Último precio').parentElement).toHaveTextContent('No verificado')
})

test('secondary quotes show publisher, dated price and exact-name evidence without the old summary', async () => {
  setup({
    ...profile,
    exchange_listing: {
      status: 'unknown',
      availability: 'available',
      explanation: 'SYNTHETIC secondary quote.',
      match_status: 'matched',
      quotes: [
        {
          instrument_id: 'synthetic-common',
          source_id: 'la_republica_quotes',
          source_name: 'La República',
          superfinanciera_code: 'COSYNTH00001',
          ticker: 'SYNTHETIC',
          last_price: '1234',
          raw_price: '$ 1.234',
          currency: null,
          isin: null,
          reported_state: 'SÍ',
          retrieved_at: '2026-11-15T12:00:00Z',
          price_as_of: '2026-11-13T20:42:12Z',
          source_url:
            'https://www.larepublica.co/indicadores-economicos/movimiento-accionario/synthetic',
          stale: false,
          variation_percent: '1.19',
          volume: '35000000',
          match_type: 'exact_legal_name',
          matched_value: 'SYNTHETIC LEGAL NAME',
        },
      ],
    },
  })
  await screen.findByText('$ 1.234')
  expect(screen.getByRole('link', { name: 'Fuente: La República ↗' })).toBeVisible()
  expect(screen.getByText(/Razón social EXACTA/)).toHaveTextContent('SYNTHETIC LEGAL NAME')
  expect(screen.queryByLabelText('Resumen de evidencia')).not.toBeInTheDocument()
  expect(screen.getByText('↑ +1,19%')).toBeVisible()
  expect(screen.getByText('$ 35.000.000')).toBeVisible()
  expect(screen.queryByText('Estado reportado por la fuente')).not.toBeInTheDocument()
  expect(screen.queryByText('Listado oficial verificado')).not.toBeInTheDocument()
  expect(screen.queryByText('SYNTHETIC secondary quote.')).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Fuente: La República ↗' })).toBeVisible()
})

test('an unresolved quote has a red alert inside the BVC card', async () => {
  setup()
  await screen.findByRole('heading', { name: 'Bolsa de Valores de Colombia' })
  const card = screen
    .getByRole('heading', { name: 'Bolsa de Valores de Colombia' })
    .closest('article')!
  expect(within(card).getByRole('alert')).toHaveClass('danger')
  expect(within(card).getByRole('alert')).toHaveTextContent('NIT, ANN o razón social')
})

test('hides the listing pill when any registered common-equity BVC row exists', async () => {
  // The matching row need not be on the current instruments page or satisfy UI filters.
  setup({ ...profile, has_registered_bvc_common_equity: true, instruments: [] })
  const card = (
    await screen.findByRole('heading', { name: 'Bolsa de Valores de Colombia' })
  ).closest('article')!
  expect(within(card).queryByText('Listado no verificado')).not.toBeInTheDocument()
  expect(within(card).getByText('Registrado')).toHaveClass('value-pill--present')
  expect(
    within(card).getByRole('button', { name: 'Help: Registro BVC' }),
  ).toHaveAccessibleDescription(/sin depender de la paginación ni de los filtros/)
})

test('shows the listing pill when there is no registered common-equity BVC row', async () => {
  setup({ ...profile, has_registered_bvc_common_equity: false })
  const card = (
    await screen.findByRole('heading', { name: 'Bolsa de Valores de Colombia' })
  ).closest('article')!
  expect(within(card).getByText('Listado no verificado')).toBeVisible()
})

test('multiple ordinary-share records raise a collapsed alert independent of visible instruments', async () => {
  setup({
    ...profile,
    common_equity_record_count: 2,
    has_registered_bvc_common_equity: true,
    instruments: [],
  })
  await openAlerts()
  expect(screen.getByText(/Se encontraron 2 registros de Acciones ordinarias/)).toBeVisible()
  expect(screen.queryByText(/No se ha establecido una coincidencia exacta/)).not.toBeInTheDocument()
  expect(screen.getByText('Registrado')).toBeVisible()
})

test('unresolved quotes show each provider outcome and the requested red alert', async () => {
  setup({
    ...profile,
    has_registered_bvc_common_equity: true,
    exchange_listing: {
      ...profile.exchange_listing,
      quotes: [],
      attempts: [
        {
          source_id: 'bvc_listings',
          source_name: 'BVC synthetic',
          source_url: null,
          status: 'not_configured',
          detail: 'No hay ruta verificada.',
          last_attempt_at: null,
        },
        {
          source_id: 'la_republica_quotes',
          source_name: 'La República synthetic',
          source_url:
            'https://www.larepublica.co/indicadores-economicos/movimiento-accionario/synthetic',
          status: 'no_exact_match',
          detail: 'quote_identity_missing',
          last_attempt_at: '2026-11-15T12:00:00Z',
        },
        {
          source_id: 'sfc_daily_quotes',
          source_name: 'SFC synthetic',
          source_url: null,
          status: 'unavailable',
          detail: 'sfc_quote_unavailable',
          last_attempt_at: '2026-11-15T12:01:00Z',
        },
      ],
    },
  })
  const card = (
    await screen.findByRole('heading', { name: 'Bolsa de Valores de Colombia' })
  ).closest('article')!
  expect(within(card).getByRole('alert')).toHaveTextContent(
    'No se ha establecido una coincidencia exacta por NIT, ANN o razón social con una cotización. Consulte otras fuentes; esto no confirma ausencia de acciones.',
  )
  const attempts = within(card).getByText('Fuentes de cotización (3)').closest('details')!
  expect(attempts).toHaveAttribute('open')
  expect(within(attempts).getByText('Sin identidad verificable')).toBeVisible()
  expect(within(attempts).getByText('Sin ruta verificada')).toBeVisible()
  expect(within(attempts).getByText(/La página contiene un precio/)).toBeVisible()
})

test('SFC daily averages keep their date and metric label without fabricating a ticker', async () => {
  setup({
    ...profile,
    has_registered_bvc_common_equity: true,
    exchange_listing: {
      ...profile.exchange_listing,
      quotes: [
        {
          instrument_id: 'synthetic-ann',
          source_id: 'sfc_daily_quotes',
          source_name: 'SFC',
          superfinanciera_code: 'COSYNTH00001',
          ticker: null,
          reported_legal_name: 'SYNTHETIC S.A.',
          last_price: '1234.56',
          raw_price: '1,234.56',
          currency: 'COP',
          isin: null,
          reported_state: null,
          retrieved_at: '2026-11-15T12:00:00Z',
          price_as_of: null,
          price_date: '2026-11-12',
          price_kind: 'daily_weighted_average',
          source_url: 'https://www.superfinanciera.gov.co/',
          stale: false,
          source_note: 'SYNTHETIC source classification differs.',
        },
      ],
    },
  })
  const card = (
    await screen.findByRole('heading', { name: 'Bolsa de Valores de Colombia' })
  ).closest('article')!
  expect(within(card).getByText('Precio promedio ponderado diario')).toBeVisible()
  expect(within(card).queryByText('Último precio')).not.toBeInTheDocument()
  expect(within(card).queryByText('Nemotécnico (ticker)')).not.toBeInTheDocument()
  expect(within(card).getByText('SYNTHETIC S.A.')).toBeVisible()
  expect(within(card).getByText('SYNTHETIC source classification differs.')).toBeVisible()
})
