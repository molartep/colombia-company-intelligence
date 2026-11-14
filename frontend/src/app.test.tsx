import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { SearchForm } from './components/SearchForm'
import { Search } from './pages/Search'
import { CompanyProfile } from './pages/CompanyProfile'
import { vi } from 'vitest'

function wrapper(node: React.ReactNode, path = '/') {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
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
  ).toEqual(['Legal entity', 'NIT', 'Registration status', 'Open profile'])
  const legalEntityCell = screen.getByText('SYNTHETIC ANDINA SAS').closest('td')!
  expect(legalEntityCell).not.toHaveTextContent('000123456')
  expect(within(table).getByRole('cell', { name: '000123456-7' })).toBeVisible()
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

test('profile displays available data and unchecked attributes', async () => {
  reply({
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
  })
  wrapper(
    <Routes>
      <Route path="/companies/:id" element={<CompanyProfile />} />
    </Routes>,
    '/companies/synthetic-id',
  )
  expect(await screen.findByRole('heading', { name: 'SYNTHETIC ANDINA SAS' })).toBeVisible()
  expect(screen.getByText('0011')).toBeVisible()
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
      verification_digit: null,
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
    expect(within(row).getAllByRole('cell')[1]).toHaveTextContent('Missing from record')
  }
})
