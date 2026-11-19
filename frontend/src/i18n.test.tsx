import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { DirectoryImport } from './components/DirectoryImport'
import { LanguageSwitcher } from './components/LanguageSwitcher'
import { ApiError } from './api/client'
import { uiMessage, errorMessage } from './i18n/messages'
import { createInstance } from 'i18next'
import { vi } from 'vitest'
import { App } from './App'
import i18n, { changeLanguage, detectLanguage, LANGUAGE_STORAGE_KEY } from './i18n'
import en from './i18n/locales/en.json'
import es from './i18n/locales/es.json'
import { formatCurrency, formatDecimal, formatDate } from './i18n/format'

const id = '00000000-0000-0000-0000-000000000001'
const company = {
  id,
  nit: '000123456',
  verification_digit: '7',
  legal_name: 'EMPRESA «Search» ÁRBOL S.A.S.',
  legal_form: 'Sociedad por Acciones Simplificada',
  registration_status: 'ACTIVA',
  primary_ciiu: '0011',
  department: null,
  municipality: null,
  registration: {
    registration_number: '00123',
    chamber: 'CÁMARA DE COMERCIO ORIGINAL',
    registration_date: '20200115',
  },
  attributes: {},
  sources: [],
  retrieved_at: null,
  source_updated_at: null,
  dataset_updated_at: null,
  resolution_note: '',
  conflicting_registration_count: 0,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}
const contract = {
  contract_id: 'CO1.SOURCE',
  source_identifier: 'source-row',
  process_id: 'SOURCE-PROCESS',
  reference: null,
  original_supplier_identifier: '0001234567',
  normalized_supplier_identifier: '000123456',
  supplier_document_type: 'NIT',
  match_method: 'exact_supplier_nit',
  match_status: 'verified',
  buyer: 'Entidad Mixta',
  buyer_nit: '123456789',
  description: 'Search — descripción ORIGINAL del contrato',
  value: '999999999999999999.123456',
  currency: 'COP',
  raw_status: 'enviado Proveedor',
  status: 'other',
  contract_type: 'Prestación de servicios',
  modality: 'Contratación directa',
  signature_date: '2025-01-01',
  start_date: null,
  end_date: null,
  department: 'Bogotá D.C.',
  city: 'Bogotá',
  source_url: 'https://www.datos.gov.co/d/jbjy-vk9h',
  source_link_label: 'Conjunto de datos oficial',
  retrieved_at: '2026-01-01T00:00:00Z',
  source_updated_at: null,
  evidence_id: 'source-evidence',
}
const group = (label: string) => ({ label, count: 1, values: { COP: contract.value } })
const secop = {
  company_id: id,
  company_name: company.legal_name,
  nit: company.nit,
  source_id: 'secop',
  source_url: contract.source_url,
  publisher: 'Colombia Compra Eficiente',
  outcome: 'completed_with_matches',
  run_id: id,
  run_status: 'completed',
  last_attempted_at: contract.retrieved_at,
  last_successful_at: contract.retrieved_at,
  source_updated_at: null,
  cache_age_seconds: 10,
  cache_ttl_seconds: 86400,
  error_code: null,
  warnings: [
    'Cobertura limitada al conjunto SECOP II de contratos electrónicos; no es un historial completo del Estado.',
  ],
  summary: {
    total_contracts: 1,
    total_values: { COP: contract.value },
    monetary_contracts: 1,
    missing_or_invalid_values: 0,
    unknown_currency_contracts: 0,
    zero_value_contracts: 0,
    distinct_buyers: 1,
    latest_signature_date: contract.signature_date,
    annual: [group('2025')],
    statuses: [group(contract.raw_status)],
    modalities: [group(contract.modality)],
    top_buyers: [group(contract.buyer)],
    departments: [group(contract.department)],
    executive_summary: 'Not rendered raw server prose',
  },
}
const instrument = {
  id: 'security',
  security_name: 'AO ECOPETROL S.A.',
  security_type_raw: 'Acciones ordinarias',
  security_category: 'common_equity',
  ticker: 'SOURCE',
  isin: null,
  ann_code: 'CO123456',
  issuance_number: '202501',
  exchange: 'BVC',
  rnve_registration_date: '2025-01-01',
  bvc_registration_date: null,
  listing_status: 'unknown',
  authorized_amount: '1234567890123456789.123456',
  currency: 'USD',
  credit_rating: 'AAA (col)',
  source_url: 'https://www.superfinanciera.gov.co/source',
  last_verified_at: contract.retrieved_at,
  stale: false,
  source_values: { 'Tipo de valor': 'Acciones ordinarias', 'Texto original': 'Search' },
  snapshot_id: id,
}
const markets = {
  company_id: id,
  rnve: { status: 'registered_active', match_status: 'verified' },
  exchange_listing: { status: 'unknown', explanation: '', availability: 'not_yet_checked' },
  equity_listed: null,
  ownership: { type: 'unknown', verification_status: 'not_assessed' },
  issuers: [],
  instruments: [instrument],
  sources: [],
  securities_availability: 'available',
  stale: false,
  summary: '',
  limitations: ['La forma jurídica proviene de RUES y no determina propiedad pública o privada.'],
}
const catalog = {
  source_id: 'rues',
  source_url: 'https://www.datos.gov.co/d/c82u-588k',
  verified_at: contract.retrieved_at,
  dataset_updated_at: null,
  note: '',
  groups: [
    {
      key: 'status',
      title: 'Registration status',
      description:
        'Status of this registration record, not proof of entity-wide legal standing. Distinct codes remain separate.',
      code_field: 'codigo_estado_matricula',
      label_field: 'estado_matricula',
      options: [
        { value: '01', code: '01', label: 'ACTIVA' },
        { value: '02', code: '02', label: 'Search' },
      ],
    },
  ],
}
function mount(path: string, screening: unknown = secop) {
  window.history.replaceState({}, '', path)
  const fetcher = vi.fn(async (url: string | URL | Request) => {
    const path = String(url).split('?')[0]!
    const data = path.endsWith('/parameters')
      ? catalog
      : path.endsWith('/platform')
        ? {
            checked_at: contract.retrieved_at,
            counts: { registrations: 1 },
            rues: {
              name: 'RUES / Confecámaras',
              availability: 'available',
              dataset_url: catalog.source_url,
              last_checked_at: null,
              last_updated_at: null,
            },
            sources: [],
            directory_missing: false,
            import_access: 'local',
            parameter_verified_at: contract.retrieved_at,
            parameter_options: 2,
          }
        : path.endsWith('/capital-markets')
          ? markets
          : path.endsWith('/securities')
            ? {
                items: [instrument],
                total: 1,
                unfiltered_total: 1,
                page: 1,
                page_size: 10,
                has_more: false,
                availability: 'available',
              }
            : path.endsWith('/secop')
              ? screening
              : path.endsWith('/contracts')
                ? {
                    items: [contract],
                    total: 1,
                    page: 1,
                    page_size: 5,
                    has_more: false,
                    run_id: id,
                  }
                : path.endsWith('/sources')
                  ? []
                  : path === '/api/v1/companies'
                    ? {
                        items: [
                          {
                            ...company,
                            chamber: 'CÁMARA ORIGINAL',
                            registration_number: '00001',
                            registration_date: '20200115',
                            renewal_date: null,
                            match_type: 'exact_nit',
                            evidence: [],
                            data_source: 'rues',
                          },
                        ],
                        page: 1,
                        page_size: 20,
                        has_more: false,
                        stale: false,
                        warning: null,
                      }
                    : company
    return { ok: true, status: 200, json: async () => structuredClone(data) }
  })
  vi.stubGlobal('fetch', fetcher)
  render(
    <App
      queryClient={
        new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
      }
    />,
  )
  return fetcher
}
afterEach(() => vi.unstubAllGlobals())

test.each([
  ['/?q=Search', 'Company search', 'Búsqueda de empresas'],
  ['/parameters', 'Parameters', 'Parámetros'],
  ['/references', 'Platform References', 'Referencias de la plataforma'],
  [`/companies/${id}`, 'Company identity', 'Identidad de la empresa'],
  [`/companies/${id}?tab=capital-markets`, 'Capital Markets', 'Mercado de capitales'],
  [
    `/companies/${id}?tab=screening`,
    'SECOP II — Government Contracts',
    'SECOP II — Contratación Pública',
  ],
])('switches every page from EN to ES and back: %s', async (path, english, spanish) => {
  mount(path)
  await screen.findByRole('heading', { name: english })
  await userEvent.click(screen.getByRole('button', { name: 'Spanish' }))
  expect(await screen.findByRole('heading', { name: spanish })).toBeInTheDocument()
  expect(document.documentElement).toHaveAttribute('lang', 'es')
  expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('es')
  await userEvent.click(screen.getByRole('button', { name: 'Inglés' }))
  expect(await screen.findByRole('heading', { name: english })).toBeInTheDocument()
})

test.each([
  [
    'not_screened',
    'Not checked yet. Run a query to review this source.',
    'Aún no consultado. Ejecuta una consulta para revisar esta fuente.',
  ],
  [
    'completed_no_matches',
    'No verified contracts were found in this dataset. This does not mean the company has never contracted with the government.',
    'No se encontraron contratos verificados en este conjunto de datos. Esto no significa que la empresa nunca haya contratado con el Estado.',
  ],
  [
    'source_unavailable',
    'Source unavailable. Contract participation could not be checked.',
    'Fuente no disponible. No se pudo comprobar si existen contratos.',
  ],
  [
    'failed',
    'The query could not be completed. There is no finding about the absence of contracts.',
    'La consulta no se pudo completar. No hay una conclusión sobre ausencia de contratos.',
  ],
])('localizes screening state without inventing results: %s', async (outcome, english, spanish) => {
  mount(`/companies/${id}?tab=screening`, { ...secop, outcome, summary: null })
  expect(await screen.findByText(english)).toBeInTheDocument()
  expect(
    screen.queryByRole('complementary', { name: 'SECOP query summary' }),
  ).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Spanish' }))
  expect(await screen.findByText(spanish)).toBeInTheDocument()
})

test('source company values and source taxonomy labels stay exact in both languages', async () => {
  mount('/parameters')
  expect(await screen.findByRole('cell', { name: 'Search' })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Spanish' }))
  expect(screen.getByRole('cell', { name: 'Search' })).toBeInTheDocument()
  expect(screen.getByRole('cell', { name: 'ACTIVA' })).toBeInTheDocument()
})

test('SECOP source values keep their original casing while labels and amounts localize', async () => {
  const fetcher = mount(`/companies/${id}?tab=screening`)
  await screen.findByRole('cell', { name: contract.description })
  const count = fetcher.mock.calls.length
  for (const value of [
    contract.description,
    contract.raw_status,
    contract.modality,
    contract.buyer,
  ])
    expect(screen.getByRole('cell', { name: value })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Spanish' }))
  for (const value of [
    contract.description,
    contract.raw_status,
    contract.modality,
    contract.buyer,
  ])
    expect(screen.getByRole('cell', { name: value })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: company.legal_name })).toBeInTheDocument()
  expect(fetcher.mock.calls.length).toBe(count)
  expect(screen.getByRole('option', { name: contract.raw_status })).toHaveValue(contract.raw_status)
})

test('SFC security names, source classifications and report fields are never translated', async () => {
  mount(`/companies/${id}?tab=capital-markets`)
  await screen.findByText(instrument.security_name)
  await userEvent.click(screen.getByRole('button', { name: 'Spanish' }))
  expect(screen.getByText(instrument.security_name)).toBeInTheDocument()
  expect(screen.getByText('AAA (col)')).toBeInTheDocument()
  expect(screen.getByText('Search')).toBeInTheDocument()
})

test('detects saved preferences, supported browser languages, and Spanish fallback safely', () => {
  expect(detectLanguage({ getItem: () => 'en' }, ['es-CO'])).toBe('en')
  expect(detectLanguage({ getItem: () => 'es' }, ['en-US'])).toBe('es')
  expect(detectLanguage({ getItem: () => 'invalid' }, ['fr-FR', 'en-GB'])).toBe('en')
  expect(detectLanguage(undefined, ['fr-FR'])).toBe('es')
  expect(
    detectLanguage(
      {
        getItem: () => {
          throw Error('blocked')
        },
      },
      ['es-CO'],
    ),
  ).toBe('es')
})

test('language switching works even when preference storage is blocked', async () => {
  mount('/')
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw Error('blocked')
  })
  await userEvent.click(screen.getByRole('button', { name: 'Spanish' }))
  expect(await screen.findByRole('link', { name: 'Parámetros' })).toBeInTheDocument()
})

test('locale files have identical nonempty keys and interpolation variables', () => {
  const flatten = (obj: object, prefix = ''): Record<string, string> =>
    Object.fromEntries(
      Object.entries(obj).flatMap(([key, value]) =>
        typeof value === 'object'
          ? Object.entries(flatten(value as object, prefix + key + '.'))
          : [[prefix + key, String(value)]],
      ),
    )
  const a = flatten(en),
    b = flatten(es)
  expect(Object.keys(a).sort()).toEqual(Object.keys(b).sort())
  for (const [key, value] of Object.entries(a)) {
    expect(value.trim()).not.toBe('')
    expect(b[key]!.trim()).not.toBe('')
    expect(value.match(/{{.*?}}/g)?.sort()).toEqual(b[key]!.match(/{{.*?}}/g)?.sort())
  }
})

test('missing English keys fall back to Spanish', async () => {
  const instance = createInstance()
  await instance.init({
    ...i18n.options,
    lng: 'en',
    resources: { en: { translation: {} }, es: { translation: { sample: 'Texto de respaldo' } } },
    initAsync: false,
  })
  expect(instance.t('sample')).toBe('Texto de respaldo')
})

test('decimal and currency formatting preserve all digits and never convert currencies', async () => {
  const value = '999999999999999999.123456'
  expect(formatDecimal(value)).toBe('999,999,999,999,999,999.123456')
  expect(formatDecimal('1.2300e2')).toBe('123.00')
  expect(formatDecimal('not a decimal')).toBe('not a decimal')
  expect(formatCurrency(value, 'USD')).toContain('999,999,999,999,999,999.123456')
  expect(formatCurrency(value, 'USD')).toContain('USD')
  await changeLanguage('es')
  expect(formatDecimal(value)).toBe('999.999.999.999.999.999,123456')
  expect(formatCurrency(value, 'USD')).toContain('USD')
  expect(formatDate('2025-01-01')).toContain('2025')
  expect(formatDate('not-a-date')).toBe('not-a-date')
  expect(formatDate('2025-02-30')).toBe('2025-02-30')
  expect(value).toBe('999999999999999999.123456')
})

test('an existing upload validation notice switches languages without clearing the form', async () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <LanguageSwitcher />
      <DirectoryImport />
    </QueryClientProvider>,
  )
  await userEvent
    .setup({ applyAccept: false })
    .upload(screen.getByLabelText(/Official issuer XLSX/), new File(['invalid'], 'invalid.txt'))
  expect(screen.getByRole('alert')).toHaveTextContent('Choose an XLSX file no larger than 10 MiB.')
  await userEvent.click(screen.getByRole('button', { name: 'Spanish' }))
  expect(screen.getByRole('alert')).toHaveTextContent('Elige un archivo XLSX de máximo 10 MiB.')
})

test('API failures localize by code and unknown source prose remains original', async () => {
  const error = new ApiError(
    'Source message must remain unchanged internally',
    'source_timeout',
    503,
  )
  expect(errorMessage(error)).toBe('The official source is temporarily unavailable.')
  await changeLanguage('es')
  expect(errorMessage(error)).toBe('La fuente oficial no está disponible temporalmente.')
  expect(error.message).toBe('Source message must remain unchanged internally')
  expect(uiMessage('Search')).toBe('Search')
  expect(uiMessage('ACTIVA')).toBe('ACTIVA')
})

test('BVC search help uses the requested short copy in both languages', async () => {
  mount('/?q=Search')
  expect(
    screen.getByRole('button', { name: 'Help: BVC registration' }),
  ).toHaveAccessibleDescription(
    "Finds companies with registered common stocks in Colombia's stock market (BVC).",
  )
  await userEvent.click(screen.getByRole('button', { name: 'Spanish' }))
  expect(screen.getByRole('button', { name: 'Ayuda: Registro BVC' })).toHaveAccessibleDescription(
    'Encuentra compañías con acciones ordinarias registradas en la bolsa de valores de Colombia (BVC).',
  )
})

test('technical terminology stays consistent in the Spanish interface catalog', () => {
  expect(JSON.stringify(es)).not.toMatch(/instantánea|caché|analizador/i)
  expect(es.fields.names.snapshots).toBe('Snapshots')
  expect(es.marketSources.snapshot).toBe('Snapshot')
  expect(es.governmentContracts.cache).toBe('Cache:')
  expect(
    es.advanced.theExistingParserRejectsOversizedArchivesFormulasMacrosExternalWorkbook,
  ).toContain('parser')
  expect(es.advanced['5CapitalMarketsRetrievalAndQuoteFallback']).toContain('fallback')
  expect(es.advanced['6RuntimeBoundariesAndAdministration']).toContain('Runtime')
})

test('legacy Advanced URL redirects to References and navigation uses the new URL', async () => {
  mount('/advanced')
  await screen.findByRole('heading', { name: 'Platform References' })
  expect(window.location.pathname).toBe('/references')
  expect(screen.getByRole('link', { name: 'Platform References' })).toHaveAttribute(
    'href',
    '/references',
  )
})
