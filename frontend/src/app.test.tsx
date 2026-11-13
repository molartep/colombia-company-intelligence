import { render, screen, waitFor } from '@testing-library/react'
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

test('search form submits and debounces edits', async () => {
  const onSearch = vi.fn()
  render(<SearchForm onSearch={onSearch} />)
  await userEvent.type(screen.getByLabelText('Company name or NIT'), 'SYNTHETIC')
  expect(onSearch).not.toHaveBeenCalled()
  await waitFor(() => expect(onSearch).toHaveBeenCalledWith('SYNTHETIC'), { timeout: 1500 })
  await userEvent.click(screen.getByRole('button', { name: /Search/ }))
  expect(onSearch).toHaveBeenCalledTimes(2)
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
  expect(screen.getByText('NIT 000123456-7')).toBeVisible()
  expect(screen.getByText('Unavailable in source')).toBeVisible()
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
