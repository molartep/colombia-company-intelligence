import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { GovernmentInvolvement, RaePage, RaeMethodology } from './components/GovernmentInvolvement'
import { changeLanguage } from './i18n'
import { readFileSync } from 'node:fs'
import type { Involvement } from './types/governmentInvolvement'

// Tests share the visual-review fixture; production builds only receive frontend/.
const fixture = JSON.parse(
  readFileSync('../docs/design/fixtures/rae-demo.json', 'utf8'),
) as Involvement
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
  expect(await screen.findByText(/Company reasoning is disabled/)).toBeVisible()
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
  await userEvent.click(screen.getByRole('button', { name: 'Recent participation — Documented' }))
  expect(screen.getAllByText(/Demonstration data/)).toHaveLength(2)
  expect(
    within(screen.getByRole('dialog')).getByRole('button', {
      name: 'Recent participation — Documented',
    }),
  ).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByText(/Signature 2026-05-14/, { selector: 'strong' })).toBeInTheDocument()
})

test('standalone general route has methodology without requesting company evidence', () => {
  const fetch = vi.fn()
  vi.stubGlobal('fetch', fetch)
  wrap(<RaePage />, '/methodology/rae')
  expect(screen.getByRole('heading', { level: 1, name: 'Government Involvement' })).toBeVisible()
  expect(fetch).not.toHaveBeenCalled()
})

test('Spanish methodology and missing tree', async () => {
  await changeLanguage('es')
  render(
    <RaeMethodology
      value={{ ...fixture, decisions: [{ ...fixture.decisions[0]!, evidence_tree: null }] }}
    />,
  )
  await userEvent.click(screen.getByText('Acerca de Rainbird RAE'))
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

test('live decisions retain evidence and scoped source links on failed refresh', async () => {
  const live: Involvement = {
    ...fixture,
    status: 'completed',
    company_id: 'company',
    screening_run_id: 'run',
    source: { ...fixture.source, evaluation_is_stale: true },
    decisions: fixture.decisions.map((item) => ({
      ...item,
      source_references: [
        {
          contract_id: 'CONTRACT',
          evidence_id: 'evidence',
          source_url: 'https://www.datos.gov.co/d/jbjy-vk9h',
          observed_at: '2026-11-26T15:00:00Z',
        },
      ],
    })),
  }
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => live })
      .mockRejectedValueOnce(new Error('Rae unavailable')),
  )
  wrap(<GovernmentInvolvement companyId="company" runId="run" />)
  expect(await screen.findByText(/Previous Rae findings retained/)).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: 'Refresh reasoning' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Previous findings remain available')
  expect(screen.getAllByText('Documented')).toHaveLength(3)
  await userEvent.click(screen.getByRole('button', { name: /Learn more/ }))
  const sources = screen.getByText('Supporting source observations')
  expect(sources.closest('details')).not.toHaveAttribute('open')
  await userEvent.click(sources)
  const links = screen.getAllByRole('link', { name: /Official source/ })
  expect(links[0]).toHaveAttribute('rel', 'noopener noreferrer')
})

test('blocked snapshot reports the actual prerequisite', async () => {
  mock({ ...fixture, status: 'blocked', decisions: [], diagnostics: ['source_snapshot_required'] })
  wrap(<GovernmentInvolvement companyId="company" runId={null} />)
  expect(
    await screen.findByText('Complete a successful SECOP II query before evaluating involvement.'),
  ).toBeVisible()
  expect(screen.queryByText(/reasoning is disabled/)).not.toBeInTheDocument()
})

test('model failures are distinct from disabled configuration', async () => {
  mock({ ...fixture, status: 'failed', decisions: [], diagnostics: ['api_unavailable'] })
  wrap(<GovernmentInvolvement companyId="company" runId="run" />)
  expect(await screen.findByText(/Decision information is temporarily unavailable/)).toBeVisible()
  expect(screen.queryByText(/reasoning is disabled/)).not.toBeInTheDocument()
})

test('reasoning cooldown explains the wait and disables repeated requests', async () => {
  const live = { ...fixture, status: 'completed' }
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => live })
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ error: { code: 'invalid_request', message: 'Wait' } }), {
          status: 429,
          headers: { 'Retry-After': '30' },
        }),
      ),
  )
  wrap(<GovernmentInvolvement companyId="company" runId="run" />)
  await userEvent.click(await screen.findByRole('button', { name: 'Refresh reasoning' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('refresh cooldown')
  expect(await screen.findByRole('button', { name: 'Refresh in 30 s' })).toBeDisabled()
  expect(screen.getAllByText('Documented')).toHaveLength(3)
})

test('lookback edits hide conclusions and do not request evaluation until Apply', async () => {
  const fetcher = vi.fn().mockImplementation(async (path: string) => ({
    ok: true,
    json: async () => ({
      ...fixture,
      evaluation: {
        ...fixture.evaluation,
        lookback_months: Number(new URL(path, 'http://test').searchParams.get('lookback_months')),
      },
    }),
  }))
  vi.stubGlobal('fetch', fetcher)
  wrap(<GovernmentInvolvement companyId="company" runId="run" />)
  expect(await screen.findAllByText('Documented')).toHaveLength(3)
  expect(screen.getByRole('spinbutton', { name: 'Lookback period' })).toHaveValue(24)
  expect(screen.getByRole('slider')).toHaveAttribute('min', '1')
  expect(screen.getByRole('slider')).toHaveAttribute('max', '120')
  fireEvent.change(screen.getByRole('slider'), { target: { value: '12' } })
  expect(screen.getByRole('spinbutton')).toHaveValue(12)
  expect(screen.queryByText('Documented')).not.toBeInTheDocument()
  expect(screen.getAllByLabelText('Results awaiting evaluation')).toHaveLength(4)
  expect(fetcher).toHaveBeenCalledTimes(1)
  await userEvent.click(screen.getByRole('button', { name: 'Apply' }))
  expect(await screen.findAllByText('Documented')).toHaveLength(3)
  expect(fetcher).toHaveBeenCalledTimes(2)
  expect(fetcher.mock.calls[1]?.[0]).toContain('lookback_months=12')
  await userEvent.click(screen.getByRole('button', { name: /Learn more/ }))
  expect(screen.getByRole('link', { name: /Open in new tab/ })).toHaveAttribute(
    'href',
    expect.stringContaining('lookback_months=12'),
  )
})

test('typed lookback is validated without changing applied results or calling the API', async () => {
  mock(fixture)
  wrap(<GovernmentInvolvement companyId="company" runId="run" />)
  await screen.findAllByText('Documented')
  fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '121' } })
  expect(screen.getByRole('alert')).toHaveTextContent('1 to 120 months')
  expect(screen.getByRole('button', { name: 'Apply' })).toBeDisabled()
  expect(fetch).toHaveBeenCalledTimes(1)
  fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '24' } })
  expect(screen.getAllByText('Documented')).toHaveLength(3)
  expect(screen.queryByRole('button', { name: 'Apply' })).not.toBeInTheDocument()
  expect(fetch).toHaveBeenCalledTimes(1)
})

test('popup uses matching outcome pills, separate sufficiency guide and dismisses only on backdrop', async () => {
  mock(fixture)
  wrap(<GovernmentInvolvement companyId="company" runId="run" />)
  await screen.findAllByText('Documented')
  expect(screen.getByRole('link', { name: "Powered by Rainbird AI's RAE." })).toHaveAttribute(
    'href',
    'https://docs.rainbird.ai/rainbird',
  )
  expect(screen.queryByText(/Independent, descriptive conclusions/)).not.toBeInTheDocument()
  expect(screen.queryByText('Explainable decisions · Rainbird Rae')).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: /Learn more/ }))
  const dialog = screen.getByRole('dialog', { name: 'Government Involvement' })
  expect(within(dialog).getByRole('heading', { name: 'Evidence sufficiency' })).toBeVisible()
  expect(within(dialog).getByText('Required facts are unavailable.')).toBeVisible()
  expect(
    within(dialog)
      .getAllByText('Documented')
      .every((item) => item.classList.contains('present')),
  ).toBe(true)
  expect(screen.queryByText('Evidence interpretation and scope')).not.toBeInTheDocument()
  fireEvent.click(within(dialog).getByText('Why this conclusion'))
  expect(dialog).toBeVisible()
  fireEvent(dialog, new MouseEvent('pointerdown', { bubbles: true, clientX: -10, clientY: -10 }))
  fireEvent.click(dialog, { clientX: -10, clientY: -10 })
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})
