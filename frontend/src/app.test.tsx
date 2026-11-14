import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { SearchForm } from './components/SearchForm'
import { Search } from './pages/Search'
import { CompanyProfile } from './pages/CompanyProfile'
import { SiteHeader } from './components/SiteHeader'
import { vi } from 'vitest'

function wrapper(
  node: React.ReactNode,
  path = '/',
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
) {
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>{node}</MemoryRouter>
    </QueryClientProvider>,
  )
}
function reply(body: unknown, status = 200) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: status === 200, status, json: async () => body }),
  )
}
afterEach(() => vi.unstubAllGlobals())

test('search form waits for submission even after typing pauses', () => {
  vi.useFakeTimers()
  try {
    const onSearch = vi.fn()
    render(<SearchForm onSearch={onSearch} />)
    fireEvent.change(screen.getByLabelText('Company name or NIT'), {
      target: { value: 'SYNTHETIC' },
    })
    act(() => vi.advanceTimersByTime(2000))
    expect(onSearch).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: /Search/ }))
    expect(onSearch).toHaveBeenCalledExactlyOnceWith('SYNTHETIC')
  } finally {
    vi.useRealTimers()
  }
})

test('submitted search opens an animated loading popup and closes it when results arrive', async () => {
  let finish!: (value: unknown) => void
  vi.stubGlobal(
    'fetch',
    vi.fn(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    ),
  )
  wrapper(<Search />)
  await userEvent.type(screen.getByLabelText('Company name or NIT'), 'SYNTHETIC')
  expect(fetch).not.toHaveBeenCalled()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: /Search/ }))
  const dialog = await screen.findByRole('dialog', { name: 'Retrieving results' })
  expect(dialog).toBeVisible()
  expect(dialog.querySelector('img')).toHaveAttribute('src', '/retrieving-results.gif')
  expect(screen.getByRole('button', { name: /Search/ })).toBeDisabled()
  await act(async () =>
    finish({ ok: true, json: async () => ({ items: [], has_more: false, page: 1 }) }),
  )
  expect(await screen.findByText('No matching registrations')).toBeVisible()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Search/ })).toBeEnabled()
})

test('renders official result and profile link', async () => {
  reply({
    items: [
      {
        id: 'synthetic-id',
        legal_name: 'SYNTHETIC ANDINA SAS',
        nit: '000123456',
        verification_digit: '7',
        registration_status: 'ACTIVA',
        registration_date: '20200115',
        renewal_date: '20240229',
        match_type: 'exact_nit',
      },
    ],
    page: 1,
    has_more: false,
  })
  wrapper(<Search />, '/?q=000123456')
  expect(await screen.findByText('SYNTHETIC ANDINA SAS')).toHaveAttribute(
    'href',
    '/companies/synthetic-id',
  )
  const table = screen.getByRole('table')
  expect(
    within(table)
      .getAllByRole('columnheader')
      .map((heading) => heading.textContent),
  ).toEqual([
    'Legal entity',
    'NIT',
    'Registration status',
    'Registration date',
    'Renewal date',
    'Open profile',
  ])
  const legalEntityCell = screen.getByText('SYNTHETIC ANDINA SAS').closest('td')!
  expect(legalEntityCell).not.toHaveTextContent('000123456')
  expect(within(table).getByRole('cell', { name: '000123456-7' })).toBeVisible()
  expect(within(table).getByRole('cell', { name: 'Jan 15, 2020' })).toBeVisible()
  expect(within(table).getByRole('cell', { name: 'Feb 29, 2024' })).toBeVisible()
  expect(within(table).getByText('ACTIVA')).toHaveClass('registration-status--active')
  expect(screen.getByRole('button', { name: /Next/ })).toBeDisabled()
})

test('source failures are visible errors', async () => {
  reply({ error: { message: 'Official source unavailable.' } }, 503)
  wrapper(<Search />, '/?q=SYNTHETIC')
  expect(await screen.findByRole('alert')).toHaveTextContent('Official source unavailable.')
  expect(screen.queryByText('No matching registrations')).not.toBeInTheDocument()
})

test('empty results explain the dataset limitation', async () => {
  reply({ items: [], page: 1, has_more: false })
  wrapper(<Search />, '/?q=SYNTHETIC')
  expect(await screen.findByText('No matching registrations')).toBeVisible()
})

const profileFixture = {
  id: 'synthetic-id',
  legal_name: 'SYNTHETIC ANDINA SAS',
  nit: '000123456',
  registration_status: 'ACTIVA',
  primary_ciiu: '0011',
  legal_form: 'SAS',
  registration: { chamber: 'SYNTHETIC CHAMBER' },
  attributes: { securities_listing: { state: 'not_yet_checked', source_field: null } },
  sources: [],
  retrieved_at: '2025-01-20T10:00:00Z',
  source_updated_at: null,
  dataset_updated_at: null,
  resolution_note: 'Registration-scoped profile.',
  conflicting_registration_count: 0,
}

test('profile displays available data and unchecked attributes', async () => {
  reply(profileFixture)
  wrapper(
    <Routes>
      <Route path="/companies/:id" element={<CompanyProfile />} />
    </Routes>,
    '/companies/synthetic-id',
  )
  expect(await screen.findByRole('heading', { name: 'SYNTHETIC ANDINA SAS' })).toBeVisible()
  expect(screen.getByText('0011')).toBeVisible()
  expect(screen.getByText('Status:').closest('.profile-status')).toHaveTextContent('ACTIVA')
  expect(screen.getByText('NIT:').closest('.identity-line')).not.toHaveTextContent('ACTIVA')
  expect(screen.queryByText('OFFICIAL SOURCE')).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: '← Company search' })).toHaveAttribute('href', '/')
  expect(screen.getByText('SYNTHETIC CHAMBER')).toBeVisible()
  expect(screen.getByRole('link', { name: 'Sources' })).toHaveAttribute(
    'href',
    '/companies/synthetic-id?tab=sources',
  )
  await userEvent.click(screen.getByText('Attribute availability & provenance'))
  expect(screen.getByText('not yet checked')).toBeVisible()
})

test('results use the requested registration status colors and preserve missing NITs', async () => {
  const statuses = ['CANCELADA', 'NO ASIGNADO', 'EN LIQUIDACION', null]
  reply({
    items: statuses.map((status, i) => ({
      id: `synthetic-status-${i}`,
      legal_name: `SYNTHETIC STATUS COMPANY ${i}`,
      nit: null,
      verification_digit: '0',
      registration_date: null,
      renewal_date: null,
      registration_status: status,
    })),
    page: 1,
    has_more: false,
  })
  wrapper(<Search />, '/?q=SYNTHETIC')
  const table = await screen.findByRole('table')
  expect(within(table).getByText('CANCELADA')).toHaveClass('registration-status--cancelled')
  expect(within(table).getByText('NO ASIGNADO')).toHaveClass('registration-status--unassigned')
  expect(within(table).getByText('EN LIQUIDACION')).toHaveClass('registration-status--other')
  for (const row of within(table).getAllByRole('row').slice(1)) {
    const cells = within(row).getAllByRole('cell')
    expect(cells[1]).toBeEmptyDOMElement()
    expect(cells[3]).toBeEmptyDOMElement()
    expect(cells[4]).toBeEmptyDOMElement()
  }
})

test('profile uses status colors, missing pills, readable dates and review flags', async () => {
  reply({
    ...profileFixture,
    nit: null,
    verification_digit: '0',
    registration_status: 'CANCELADA',
    legal_form: null,
    primary_ciiu: null,
    registration: {
      registration_date: '20240229',
      renewal_date: '00000000',
      cancellation_date: null,
    },
    source_updated_at: '1900-01-01T04:56:16Z',
    attributes: {
      legal_name: { state: 'present', source_field: 'razon_social' },
      nit: { state: 'missing_from_record', source_field: 'nit' },
    },
  })
  wrapper(
    <Routes>
      <Route path="/companies/:id" element={<CompanyProfile />} />
    </Routes>,
    '/companies/synthetic-id',
  )
  await screen.findByRole('heading', { name: 'SYNTHETIC ANDINA SAS' })
  const nit = screen.getByText('NIT:').closest('.profile-nit')!
  expect(within(nit as HTMLElement).getByText('Missing')).toHaveClass('value-pill--missing')
  expect(nit).not.toHaveTextContent('-0')
  expect(screen.queryByRole('button', { name: 'Copy NIT' })).not.toBeInTheDocument()
  expect(screen.getByText('CANCELADA')).toHaveClass('registration-status--cancelled')
  const identity = screen.getByRole('heading', { name: 'Company identity' }).closest('article')!
  expect(within(identity).queryByText('Department')).not.toBeInTheDocument()
  expect(within(identity).queryByText('Municipality')).not.toBeInTheDocument()
  expect(within(identity).getAllByText('Missing')).toHaveLength(2)
  expect(within(identity).getAllByText('Missing')[0]).toHaveClass('value-pill--missing')
  expect(screen.queryByText(/Registration-scoped profile/)).not.toBeInTheDocument()
  expect(
    screen.queryByText(/Dates are shown in their original source format/),
  ).not.toBeInTheDocument()
  expect(screen.getByText('Feb 29, 2024')).toHaveAttribute('datetime', '2024-02-29')
  expect(screen.getByTitle('Source value: 00000000')).toHaveClass('value-pill--review')
  expect(screen.getByTitle('Source value: 1900-01-01T04:56:16Z')).toHaveClass('value-pill--review')
  expect(screen.queryByText(/Missing from record/i)).not.toBeInTheDocument()
  await userEvent.click(screen.getByText('Attribute availability & provenance'))
  expect(screen.getByText('Present')).toHaveClass('value-pill--present')
})

test('Sources shows availability dots and flags placeholder record updates', async () => {
  const sources = [
    { id: 'synthetic-available', name: 'SYNTHETIC AVAILABLE SOURCE', availability: 'available' },
    { id: 'synthetic-failed', name: 'SYNTHETIC FAILED SOURCE', availability: 'failed_to_retrieve' },
  ].map((source) => ({
    ...source,
    description: 'Synthetic source fixture',
    dataset_url: 'https://example.test/dataset',
  }))
  const records = [
    {
      id: 'synthetic-record',
      external_record_id: 'synthetic-row',
      source_id: 'synthetic-available',
      retrieved_at: '2025-01-20T10:00:00Z',
      source_updated_at: '1900-01-01T00:00:00Z',
      payload_hash: 'synthetic-hash',
      fields: {},
      source_url: 'https://example.test/dataset',
    },
  ]
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () => (url.endsWith('/sources') ? records : { ...profileFixture, sources }),
    })),
  )
  wrapper(
    <Routes>
      <Route path="/companies/:id" element={<CompanyProfile />} />
    </Routes>,
    '/companies/synthetic-id?tab=sources',
  )
  await screen.findByRole('heading', { name: 'Records & provenance' })
  expect(screen.queryByText('AUDITABLE BY DESIGN')).not.toBeInTheDocument()
  expect(
    screen.getByText('Availability: available').querySelector('.availability-dot--available'),
  ).toBeInTheDocument()
  expect(
    screen
      .getByText('Availability: failed to retrieve')
      .querySelector('.availability-dot--unavailable'),
  ).toBeInTheDocument()
  expect(await screen.findByTitle('Source value: 1900-01-01T00:00:00Z')).toHaveClass(
    'value-pill--review',
  )
})

it.each(['name', 'arrow'])(
  'restores the cached search page after navigating profile tabs via the %s link',
  async (link) => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } })
    const query = 'SYNTHETIC COMPANY'
    const cached = {
      items: [{ ...profileFixture, match_type: 'partial_name' }],
      page: 3,
      page_size: 20,
      has_more: true,
      stale: false,
    }
    client.setQueryData(['search', query, 3], cached, { updatedAt: Date.now() - 120_000 })
    client.setQueryData(['search', query, 1], { ...cached, page: 1 })
    const fetchMock = vi.fn(async (url: string) => ({
      ok: true,
      json: async () => {
        if (url.startsWith('/api/v1/companies?'))
          return {
            ...cached,
            page: 1,
            items: [{ ...cached.items[0], legal_name: 'SYNTHETIC REFRESHED SAS' }],
          }
        return url.endsWith('/sources') ? [] : profileFixture
      },
    }))
    vi.stubGlobal('fetch', fetchMock)
    wrapper(
      <Routes>
        <Route path="/" element={<Search />} />
        <Route path="/companies/:id" element={<CompanyProfile />} />
      </Routes>,
      '/?q=SYNTHETIC+COMPANY&page=3',
      client,
    )
    expect(screen.getByRole('table')).toBeVisible()
    expect(fetchMock).not.toHaveBeenCalled()
    await userEvent.click(
      screen.getByRole('link', {
        name: link === 'name' ? 'SYNTHETIC ANDINA SAS' : 'View SYNTHETIC ANDINA SAS',
      }),
    )
    await screen.findByRole('heading', { name: 'SYNTHETIC ANDINA SAS' })
    await userEvent.click(screen.getByRole('link', { name: 'Sources' }))
    await screen.findByRole('heading', { name: 'Records & provenance' })
    expect(screen.getByRole('link', { name: '← Company search' })).toHaveAttribute(
      'href',
      '/?q=SYNTHETIC+COMPANY&page=3',
    )
    await userEvent.click(screen.getByRole('link', { name: 'Overview' }))
    await userEvent.click(screen.getByRole('link', { name: '← Company search' }))
    expect(screen.getByRole('table')).toBeVisible()
    expect(screen.getByLabelText('Company name or NIT')).toHaveValue(query)
    expect(screen.getByText('Page 3', { exact: true })).toBeVisible()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(
      fetchMock.mock.calls.filter(([url]) => url.startsWith('/api/v1/companies?')),
    ).toHaveLength(0)
    // A deliberate new submission must still fetch, even when page 1 is already cached.
    await userEvent.click(screen.getByRole('button', { name: /Search/ }))
    expect(await screen.findByText('SYNTHETIC REFRESHED SAS')).toBeVisible()
    expect(
      fetchMock.mock.calls.filter(([url]) => url.startsWith('/api/v1/companies?')),
    ).toHaveLength(1)
    client.clear()
  },
)

test('home uses the custom logo and correct accessible social profile links', () => {
  wrapper(
    <>
      <SiteHeader />
      <Search />
    </>,
  )
  expect(screen.queryByText(/A clearer view of/)).not.toBeInTheDocument()
  expect(screen.queryByText(/Start with identity/)).not.toBeInTheDocument()
  expect(screen.getByRole('img', { name: /Colombia outline/ })).toHaveAttribute(
    'src',
    '/colombia-network-logo.png',
  )
  expect(screen.getByRole('link', { name: 'Colombia Company Intelligence home' })).toHaveAttribute(
    'href',
    '/',
  )
  const social = screen.getByRole('navigation', { name: 'Social media' })
  expect(within(social).getByRole('link', { name: 'Martin Olarte on GitHub' })).toHaveAttribute(
    'href',
    'https://github.com/molartep',
  )
  const linkedIn = within(social).getByRole('link', { name: 'Martin Olarte on LinkedIn' })
  expect(linkedIn).toHaveAttribute('href', 'https://www.linkedin.com/in/martin-olarte-pallares/')
  for (const link of within(social).getAllByRole('link')) {
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  }
  expect(screen.getByLabelText('Company name or NIT')).toBeVisible()
})
