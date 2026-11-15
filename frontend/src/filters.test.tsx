import { render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'
import { Search } from './pages/Search'
import { Parameters } from './pages/Parameters'
import { CompanyProfile } from './pages/CompanyProfile'
import { SiteHeader } from './components/SiteHeader'
import { filterParams, readFilters, searchKey } from './api/filters'
import type { ParameterCatalog } from './types'

const catalog: ParameterCatalog = {
  source_id: 'rues-c82u-588k',
  source_url: 'https://www.datos.gov.co/d/c82u-588k',
  verified_at: '2026-11-14T12:00:00Z',
  dataset_updated_at: '2026-11-06T20:49:30Z',
  note: 'Observed source values; this snapshot may lag publisher changes.',
  groups: [
    {
      key: 'status',
      title: 'Registration status',
      code_field: 'codigo_estado_matricula',
      label_field: 'estado_matricula',
      description: 'Status of this registration, not entity-wide standing.',
      options: [
        { value: '01', code: '01', label: 'ACTIVA' },
        { value: '03', code: '03', label: 'CANCELADA' },
        { value: '4', code: '4', label: null },
      ],
    },
    {
      key: 'chamber',
      title: 'Chamber of Commerce',
      code_field: 'codigo_camara',
      label_field: 'camara_comercio',
      description: 'Registering chamber, not company location.',
      options: [{ value: '04', code: '04', label: 'BOGOTA' }],
    },
    {
      key: 'organization',
      title: 'Legal organization',
      code_field: 'codigo_organizacion_juridica',
      label_field: 'organizacion_juridica',
      description: 'Legal organization reported by RUES.',
      options: [
        { value: '01', code: '01', label: 'PERSONA NATURAL' },
        { value: '16', code: '16', label: 'SOCIEDADES POR ACCIONES SIMPLIFICADAS SAS' },
      ],
    },
    {
      key: 'category',
      title: 'Registration category',
      code_field: 'codigo_categoria_matricula',
      label_field: 'categoria_matricula',
      description: 'Reported registration category.',
      options: [{ value: '01', code: '01', label: 'SOCIEDAD ó PERSONA JURIDICA PRINCIPAL ó ESAL' }],
    },
  ],
}
function setup(
  path = '/',
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
) {
  const requests: URL[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string) => {
      const url = new URL(path, 'http://test')
      requests.push(url)
      return {
        ok: true,
        json: async () =>
          url.pathname.endsWith('/parameters')
            ? catalog
            : {
                items: [
                  {
                    id: 'synthetic',
                    legal_name: 'SYNTHETIC TEST SAS',
                    nit: null,
                    registration_status: 'ACTIVA',
                  },
                ],
                has_more: url.searchParams.get('page') !== '2',
                page: Number(url.searchParams.get('page')),
                page_size: 20,
              },
      }
    }),
  )
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <SiteHeader />
        <Routes>
          <Route path="/" element={<Search />} />
          <Route path="/parameters" element={<Parameters />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return requests
}
afterEach(() => vi.unstubAllGlobals())

test('all advanced filters are submit-only, reset pagination and survive Next', async () => {
  const requests = setup('/?q=TEST&page=2')
  await screen.findByText('SYNTHETIC TEST SAS')
  expect(requests).toHaveLength(1)
  expect(screen.getByText('Advanced filters').closest('details')).not.toHaveAttribute('open')
  await userEvent.click(screen.getByText('Advanced filters'))
  await screen.findByText('Registration category')
  const searchButtons = screen.getAllByRole('button', { name: /^Search/ })
  expect(searchButtons).toHaveLength(2)
  for (const button of searchButtons) {
    expect(button).toHaveClass('search-submit')
    expect(button).toHaveAttribute('type', 'submit')
  }
  expect(
    screen.queryByText('Apply to all matching source records when you submit Search.'),
  ).not.toBeInTheDocument()
  expect(
    screen.queryByText('Multiple values within a filter use OR; different filters use AND.'),
  ).not.toBeInTheDocument()
  for (const label of [
    'Registration status',
    'Chamber of Commerce',
    'Legal organization',
    'Registration category',
  ]) {
    await userEvent.click(screen.getByLabelText(label, { selector: 'summary' }))
  }
  for (const label of [
    '01 · ACTIVA',
    '03 · CANCELADA',
    '04 · BOGOTA',
    '16 · SOCIEDADES POR ACCIONES SIMPLIFICADAS SAS',
    '01 · SOCIEDAD ó PERSONA JURIDICA PRINCIPAL ó ESAL',
  ]) {
    await userEvent.click(screen.getByRole('checkbox', { name: label }))
  }
  await userEvent.selectOptions(screen.getByLabelText('Code matching'), 'prefix')
  await userEvent.type(screen.getByLabelText('Economic activity / CIIU'), '62')
  await userEvent.selectOptions(screen.getByLabelText('Activity scope'), 'any')
  const { fireEvent } = await import('@testing-library/react')
  for (const [label, value] of [
    ['Registration date from', '2000-01-01'],
    ['Registration date to', '2025-12-31'],
    ['Renewal date from', '2024-01-01'],
    ['Renewal date to', '2025-12-31'],
  ] as const) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } })
  }
  await userEvent.type(screen.getByLabelText('Last renewed year'), '2024')
  await userEvent.selectOptions(screen.getByLabelText('Year matching'), 'minimum')
  expect(requests.filter((url) => url.pathname.endsWith('/companies'))).toHaveLength(1)
  await userEvent.click(screen.getAllByRole('button', { name: /^Search/ }).at(-1)!)
  await waitFor(() =>
    expect(requests.filter((url) => url.pathname.endsWith('/companies'))).toHaveLength(2),
  )
  const query = requests.at(-1)!.searchParams
  expect(query.get('page')).toBe('1')
  expect(query.getAll('status')).toEqual(['01', '03'])
  for (const [key, value] of Object.entries({
    chamber: '04',
    organization: '16',
    category: '01',
    ciiu: '62',
    ciiu_match: 'prefix',
    ciiu_scope: 'any',
    registration_from: '2000-01-01',
    registration_to: '2025-12-31',
    renewal_from: '2024-01-01',
    renewal_to: '2025-12-31',
    renewed_year: '2024',
    renewed_year_mode: 'minimum',
  })) {
    expect(query.get(key)).toBe(value)
  }
  await waitFor(() => expect(screen.getByRole('button', { name: /Next/ })).toBeEnabled())
  await userEvent.click(screen.getByRole('button', { name: /Next/ }))
  await waitFor(() => expect(requests.at(-1)!.searchParams.get('page')).toBe('2'))
  expect(requests.at(-1)!.searchParams.getAll('status')).toEqual(['01', '03'])
  expect(requests.at(-1)!.searchParams.get('renewal_from')).toBe('2024-01-01')
})

test('URL restores fixed options, clear is submit-only, and help is keyboard accessible', async () => {
  const requests = setup('/?q=TEST&status=03&ciiu=0011&renewed_year=2024')
  await screen.findByText('SYNTHETIC TEST SAS')
  await userEvent.click(screen.getByText('Advanced filters'))
  await screen.findByText('Registration category')
  await userEvent.click(screen.getByLabelText('Registration status', { selector: 'summary' }))
  expect(screen.getByRole('checkbox', { name: '03 · CANCELADA' })).toBeChecked()
  expect(screen.getByLabelText('Economic activity / CIIU')).toHaveValue('0011')
  const help = screen.getByRole('button', { name: 'Help: Registration status' })
  help.focus()
  expect(help).toHaveFocus()
  expect(document.getElementById(help.getAttribute('aria-describedby')!)).toHaveTextContent(
    'not entity-wide standing',
  )
  const count = requests.length
  await userEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
  expect(requests).toHaveLength(count)
  expect(screen.getByRole('checkbox', { name: '03 · CANCELADA' })).not.toBeChecked()
  await userEvent.click(screen.getAllByRole('button', { name: /^Search/ }).at(-1)!)
  await waitFor(() => expect(requests).toHaveLength(count + 1))
  expect(requests.at(-1)!.searchParams.has('status')).toBe(false)
  expect(requests.at(-1)!.searchParams.has('ciiu')).toBe(false)
})

test('parameters tab shows source code meanings and missing descriptions without invention', async () => {
  setup()
  await userEvent.click(screen.getByRole('link', { name: 'Parameters' }))
  await screen.findByRole('heading', { name: 'Parameters' })
  await screen.findByText('ACTIVA')
  expect(screen.getByRole('link', { name: 'Parameters' })).toHaveAttribute('aria-current', 'page')
  expect(screen.getByText('Description missing from source')).toBeVisible()
  const statusTable = screen
    .getByRole('heading', { name: 'Registration status' })
    .closest('section')!
  expect(within(statusTable).getByText('4')).toBeVisible()
  expect(screen.getByText(catalog.note)).toBeVisible()
  expect(screen.getByRole('link', { name: /RUES \/ Confecámaras source/ })).toHaveAttribute(
    'href',
    catalog.source_url,
  )
})

test('filter cache keys are canonical and distinct from unfiltered cached results', () => {
  const a = filterParams(
    readFilters(new URLSearchParams('status=03&status=01&status=01&ciiu=0011')),
  ).toString()
  const b = filterParams(
    readFilters(new URLSearchParams('ciiu=0011&status=01&status=03')),
  ).toString()
  expect(a).toBe(b)
  expect(searchKey('TEST', 1, a)).not.toEqual(searchKey('TEST', 1, ''))
  expect(searchKey('TEST', 1, a)).not.toEqual(searchKey('TEST', 2, a))
})

test('returning from a profile restores the filtered page without another company search', async () => {
  const urls: URL[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string) => {
      const url = new URL(path, 'http://test')
      urls.push(url)
      return {
        ok: true,
        json: async () =>
          url.pathname.endsWith('/sources')
            ? []
            : url.pathname === '/api/v1/companies/synthetic'
              ? {
                  id: 'synthetic',
                  legal_name: 'SYNTHETIC FILTERED SAS',
                  nit: null,
                  registration_status: 'CANCELADA',
                  registration: {},
                  attributes: {},
                  sources: [],
                  retrieved_at: null,
                  source_updated_at: null,
                  dataset_updated_at: null,
                }
              : {
                  items: [
                    {
                      id: 'synthetic',
                      legal_name: 'SYNTHETIC FILTERED SAS',
                      nit: null,
                      registration_status: 'CANCELADA',
                    },
                  ],
                  page: 2,
                  page_size: 20,
                  has_more: false,
                },
      }
    }),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/?q=TEST&page=2&status=03&chamber=04']}>
        <Routes>
          <Route path="/" element={<Search />} />
          <Route path="/companies/:id" element={<CompanyProfile />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  await userEvent.click(await screen.findByRole('link', { name: 'SYNTHETIC FILTERED SAS' }))
  await screen.findByRole('heading', { name: 'SYNTHETIC FILTERED SAS' })
  const back = screen.getByRole('link', { name: /Company search/ })
  expect(back).toHaveAttribute('href', '/?q=TEST&page=2&status=03&chamber=04')
  await userEvent.click(back)
  await screen.findByRole('link', { name: 'SYNTHETIC FILTERED SAS' })
  expect(screen.getByText('1 record found')).toBeVisible()
  expect(screen.getByText('Page 2')).toBeVisible()
  expect(urls.filter((url) => url.pathname === '/api/v1/companies')).toHaveLength(1)
  expect(urls[0]!.searchParams.get('status')).toBe('03')
  expect(urls[0]!.searchParams.get('chamber')).toBe('04')
})

test('parameters uses accessible table tabs and places Open filters below separate freshness lines', async () => {
  setup('/parameters')
  const tabs = await screen.findAllByRole('tab')
  expect(tabs).toHaveLength(4)
  expect(tabs[0]).toHaveTextContent('Registration status (3)')
  expect(tabs[0]).toHaveAttribute('aria-selected', 'true')
  expect(screen.queryByText('SOURCE REFERENCE')).not.toBeInTheDocument()
  expect(screen.queryByText('Other filter choices')).not.toBeInTheDocument()
  const verified = screen.getByText(/^Verified:/)
  const updated = screen.getByText(/^Dataset updated:/)
  expect(verified).not.toBe(updated)
  expect(verified.tagName).toBe('P')
  expect(updated.tagName).toBe('P')
  const open = screen.getByRole('heading', { name: 'Open filters' })
  expect(updated.compareDocumentPosition(open) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(open.compareDocumentPosition(tabs[0]!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(screen.getAllByRole('table')).toHaveLength(1)
  await userEvent.click(tabs[2]!)
  expect(screen.getByRole('tabpanel')).toHaveAccessibleName('Legal organization (2)')
  expect(screen.getByRole('tabpanel')).toHaveTextContent(
    'SOCIEDADES POR ACCIONES SIMPLIFICADAS SAS',
  )
  expect(screen.queryByRole('heading', { name: 'Registration status' })).not.toBeInTheDocument()
  await userEvent.keyboard('{ArrowRight}')
  expect(tabs[3]).toHaveFocus()
  expect(screen.getByRole('tabpanel')).toHaveAccessibleName('Registration category (1)')
  await userEvent.keyboard('{Home}')
  expect(tabs[0]).toHaveFocus()
  expect(screen.getByRole('tabpanel')).toHaveAccessibleName('Registration status (3)')
  await userEvent.keyboard('{End}')
  expect(tabs[3]).toHaveFocus()
})

test('select all allows excluding a legal organization and clearing the explicit selection', async () => {
  const requests = setup('/?q=TEST&page=1')
  await screen.findByText('SYNTHETIC TEST SAS')
  await userEvent.click(screen.getByText('Advanced filters'))
  await screen.findByText('Registration category')
  await userEvent.click(screen.getByLabelText('Legal organization', { selector: 'summary' }))
  const options = screen.getByRole('group', { name: 'Legal organization' })
  const all = within(options).getByRole('checkbox', { name: 'Select all' })
  expect(within(options).getAllByRole('checkbox')[0]).toBe(all)
  expect(all).not.toBeChecked()
  const count = requests.length
  await userEvent.click(all)
  for (const checkbox of within(options).getAllByRole('checkbox')) expect(checkbox).toBeChecked()
  await userEvent.click(within(options).getByRole('checkbox', { name: '01 · PERSONA NATURAL' }))
  expect(all).toBePartiallyChecked()
  expect(
    within(options).getByRole('checkbox', {
      name: '16 · SOCIEDADES POR ACCIONES SIMPLIFICADAS SAS',
    }),
  ).toBeChecked()
  expect(requests).toHaveLength(count)
  await userEvent.click(screen.getAllByRole('button', { name: /^Search/ }).at(-1)!)
  await waitFor(() => expect(requests).toHaveLength(count + 1))
  expect(requests.at(-1)!.searchParams.getAll('organization')).toEqual(['16'])
  // A mixed master selects everything; toggling again clears the filter to its default.
  await userEvent.click(all)
  expect(all).toBeChecked()
  await userEvent.click(all)
  for (const checkbox of within(options).getAllByRole('checkbox'))
    expect(checkbox).not.toBeChecked()
})
