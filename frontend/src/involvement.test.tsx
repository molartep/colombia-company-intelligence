import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { GovernmentInvolvement, RaePage, RaeMethodology } from './components/GovernmentInvolvement'
import { changeLanguage } from './i18n'
import demo from '../../docs/design/fixtures/rae-demo.json'
import type { Involvement } from './types/governmentInvolvement'

const fixture = demo as Involvement
function wrap(element: React.ReactNode, route = '/') {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[route]}>{element}</MemoryRouter>
    </QueryClientProvider>,
  )
}
beforeEach(async () => {
  await changeLanguage('en')
})
afterEach(() => vi.unstubAllGlobals())
function mock(value: unknown) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => value }))
}

test('disabled card never fabricates company decisions and opens shared methodology', async () => {
  mock({ ...fixture, status: 'disabled', decisions: [] })
  wrap(<GovernmentInvolvement companyId="test-company" runId="test-run" />)
  expect(await screen.findByText(/Company reasoning is not enabled/)).toBeVisible()
  expect(screen.getAllByText('Undetermined')).toHaveLength(4)
  await userEvent.click(screen.getByRole('button', { name: /Learn more/ }))
  const dialog = screen.getByRole('dialog')
  expect(dialog).toBeVisible()
  const link = screen.getByRole('link', { name: /Open in new tab/ })
  expect(link).toHaveAttribute('target', '_blank')
  expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  expect(link.getAttribute('href')).toContain('company=test-company')
  fireEvent(dialog, new Event('cancel', { bubbles: false, cancelable: true }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})

test('synthetic classifications coexist and direct selection opens evidence', async () => {
  mock(fixture)
  wrap(<GovernmentInvolvement companyId="synthetic" runId={null} />)
  expect(await screen.findAllByText('Documented')).toHaveLength(3)
  await userEvent.click(screen.getByRole('button', { name: /Recent participation/ }))
  expect(screen.getAllByText(/Demonstration data/)).toHaveLength(2)
  const summary = screen.getByText('Recent participation — Documented')
  expect(summary.closest('details')).toHaveAttribute('open')
  expect(screen.getByText(/Signature 2026-05-14/)).toBeInTheDocument()
})

test('standalone general route has methodology without requesting company evidence', () => {
  const fetch = vi.fn()
  vi.stubGlobal('fetch', fetch)
  wrap(<RaePage />, '/methodology/rae')
  expect(screen.getByRole('heading', { level: 1, name: 'Decision methodology' })).toBeVisible()
  expect(fetch).not.toHaveBeenCalled()
})

test('Spanish methodology and missing tree', async () => {
  await changeLanguage('es')
  render(
    <RaeMethodology
      value={{ ...fixture, decisions: [{ ...fixture.decisions[0]!, evidence_tree: null }] }}
    />,
  )
  expect(screen.getByText('¿Qué es Rae?')).toBeVisible()
  expect(
    screen.getByText('La evidencia de razonamiento no está disponible para esta decisión.'),
  ).toBeInTheDocument()
})

test('source stale and API errors remain separate', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('outage')))
  wrap(<GovernmentInvolvement companyId="synthetic" runId={null} />)
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Official contract evidence remains available',
  )
})
