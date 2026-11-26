import { chooseOption, openDropdown } from './testDropdown'
import fs from 'node:fs'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { vi } from 'vitest'
import type { ReactNode } from 'react'
import { Presentation } from './components/Presentation'
import { Screening } from './components/Screening'
import { CapitalMarkets } from './components/CapitalMarkets'
import { useCurrencyAmounts, useContractExport } from './presentation/context'
import { toUsd, validRate } from './presentation/currency'
import { changeLanguage } from './i18n'
import { api } from './api/client'

// Rae has its own state/accessibility tests; keep these SECOP/currency tests isolated.
vi.mock('./components/GovernmentInvolvement', () => ({ GovernmentInvolvement: () => null }))

const fixtures = JSON.parse(fs.readFileSync('../docs/design/fixtures/ui-review.json', 'utf8'))
const today = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'America/Bogota',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
}).format(new Date())
const referenceRate = {
  cop_per_usd: '4000',
  source: 'SFC TRM',
  source_url: 'https://www.datos.gov.co/d/32sa-8pi3',
  effective_date: today,
  effective_until: today,
  manual: false,
  stale: false,
  provider_failed: false,
}
function Amount() {
  const money = useCurrencyAmounts()
  return (
    <>
      <h3>{`Value (${money.currency('COP')})`}</h3>
      <strong data-testid="amount">{money.format('4000.00', 'COP')}</strong>
      <p data-testid="eur">{money.format('4000.00', 'EUR')}</p>
    </>
  )
}
function TestContractExport() {
  useContractExport(
    fixtures.id,
    'q=Árbol&raw_status=En+ejecución&run_id=snapshot&page=2&page_size=5',
    false,
  )
  return null
}
function renderPresentation(children?: ReactNode) {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <Presentation companyId={fixtures.id} companyInformation={<h1>Company</h1>}>
        {children ?? (
          <>
            <Amount />
            <TestContractExport />
          </>
        )}
      </Presentation>
    </QueryClientProvider>,
  )
}
beforeEach(async () => {
  await changeLanguage('en')
  vi.stubGlobal(
    'fetch',
    vi
      .fn<typeof fetch>()
      .mockImplementation(async () => new Response(JSON.stringify(referenceRate))),
  )
})
afterEach(() => vi.unstubAllGlobals())

test('precise division, half even and invalid rates', () => {
  expect(toUsd('999999999999999999.123456', '4000')).toBe('250000000000000.00')
  expect(toUsd('0.025', '1')).toBe('0.02')
  expect(toUsd('0.035', '1')).toBe('0.04')
  expect(toUsd('-0.035', '1')).toBe('-0.04')
  for (const value of ['0', '-1', 'NaN', '1e3', '4,000', ' 4000'])
    expect(validRate(value)).toBe(false)
})

test('permanent currency card has only COP/USD; effective TRM replaces original values in the same element', async () => {
  renderPresentation()
  const select = screen.getByRole('combobox', { name: 'Currency' })
  expect(
    within(await openDropdown(select))
      .getAllByRole('option')
      .map((o) => o.querySelector('span')?.textContent),
  ).toEqual(['COP', 'USD'])
  expect(fetch).not.toHaveBeenCalled()
  const original = screen.getByTestId('amount').textContent
  const eur = screen.getByTestId('eur').textContent
  await chooseOption(select, 'USD')
  await waitFor(() => expect(screen.getByLabelText('COP per USD')).toHaveValue('4000'))
  expect(screen.getByTestId('amount')).toHaveTextContent('≈ USD 1.00')
  expect(screen.getByTestId('amount').tagName).toBe('STRONG')
  expect(screen.getByRole('heading', { name: 'Value (USD)' })).toBeInTheDocument()
  expect(screen.queryByText(original!)).not.toBeInTheDocument()
  expect(screen.getByTestId('eur')).toHaveTextContent(eur!.replace(/\s/g, ' '))
  expect(screen.queryByLabelText('Manual rate effective date')).not.toBeInTheDocument()
  expect(screen.queryByText('Manual rate')).not.toBeInTheDocument()
  await chooseOption(select, 'COP')
  expect(screen.getByTestId('amount')).toHaveTextContent(original!.replace(/\s/g, ' '))
  expect(screen.getByRole('heading', { name: 'Value (COP)' })).toBeInTheDocument()
})

test('editing TRM marks manual mode, validates decimals and icon refresh restores the reference', async () => {
  const user = userEvent.setup()
  renderPresentation()
  await chooseOption(screen.getByRole('combobox', { name: 'Currency' }), 'USD')
  const input = await screen.findByLabelText('COP per USD')
  await waitFor(() => expect(input).toHaveValue('4000'))
  await user.clear(input)
  await user.type(input, '0')
  expect(input).toHaveAttribute('aria-invalid', 'true')
  expect(screen.getByRole('button', { name: 'Export' })).toBeDisabled()
  expect(screen.getByRole('heading', { name: 'Value (COP)' })).toBeInTheDocument()
  await user.clear(input)
  await user.type(input, '2000')
  expect(screen.getByTestId('amount')).toHaveTextContent('≈ USD 2.00')
  expect(screen.getByText('Manual rate')).toBeInTheDocument()
  const refresh = screen.getByRole('button', { name: 'Refresh reference rate' })
  expect(refresh.querySelector('svg')).toBeInTheDocument()
  expect(refresh).toHaveTextContent('')
  await user.click(refresh)
  await waitFor(() => expect(input).toHaveValue('4000'))
  expect(screen.queryByText('Manual rate')).not.toBeInTheDocument()
  expect(screen.getByTestId('amount')).toHaveTextContent('≈ USD 1.00')
})

test.each([true, false])(
  'stale or unavailable TRM retains truthful COP labels and permits manual entry (%s)',
  async (stale) => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn<typeof fetch>()
        .mockResolvedValue(
          new Response(JSON.stringify({ ...referenceRate, stale }), { status: stale ? 200 : 503 }),
        ),
    )
    renderPresentation()
    await chooseOption(screen.getByRole('combobox', { name: 'Currency' }), 'USD')
    await screen.findByText(/TRM unavailable or stale/)
    expect(screen.getByRole('heading', { name: 'Value (COP)' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Export' })).toBeDisabled()
    await userEvent.type(screen.getByLabelText('COP per USD'), '4000')
    expect(screen.getByRole('heading', { name: 'Value (USD)' })).toBeInTheDocument()
    expect(screen.getByText('Manual rate')).toBeInTheDocument()
  },
)

test('currency information is in focusable, Escape-dismissible tooltips', async () => {
  renderPresentation()
  const help = screen.getByRole('button', { name: 'Help: Currency' })
  help.focus()
  const tooltip = document.getElementById(help.getAttribute('aria-describedby')!)!
  expect(tooltip).toHaveTextContent('not historical FX')
  await userEvent.keyboard('{Escape}')
  expect(help.parentElement).toHaveAttribute('data-dismissed', 'true')
})

test('contract summaries, charts, table and detail replace money and labels without changing filters', async () => {
  const stored = JSON.stringify(fixtures.secop)
  vi.spyOn(api, 'secop').mockResolvedValue(fixtures.secop)
  vi.spyOn(api, 'secopContracts').mockResolvedValue({
    items: fixtures.contracts.slice(0, 5),
    total: 7,
    page: 1,
    page_size: 5,
    has_more: true,
    run_id: fixtures.id,
  })
  vi.spyOn(api, 'secopContract').mockResolvedValue(fixtures.contracts[0])
  renderPresentation(<Screening companyId={fixtures.id} />)
  await screen.findByRole('columnheader', { name: 'Value (COP)' })
  const requestCount = vi.mocked(api.secopContracts).mock.calls.length
  await chooseOption(screen.getByRole('combobox', { name: 'Currency' }), 'USD')
  await screen.findByRole('columnheader', { name: 'Value (USD)' })
  expect(screen.getByRole('heading', { name: 'Annual contract value (USD)' })).toBeInTheDocument()
  expect(
    screen.getByRole('heading', { name: 'Top five entities by contract value (USD)' }),
  ).toBeInTheDocument()
  const summary = screen.getByLabelText('SECOP query summary')
  expect(
    within(summary).getByRole('heading', { name: 'Total contract value (USD)' }),
  ).toBeInTheDocument()
  expect(within(summary).getAllByText(/≈/)).toHaveLength(1)
  expect(within(summary).getByText(/≈/).closest('strong')).toBeInTheDocument()
  const table = screen.getByRole('table')
  expect(within(table).queryByText('8,137,440,199.125000')).not.toBeInTheDocument()
  expect(within(table).getAllByText(/≈/)).toHaveLength(5)
  expect(vi.mocked(api.secopContracts).mock.calls.length).toBe(requestCount)
  await userEvent.click(screen.getByRole('button', { name: fixtures.contracts[0].contract_id }))
  const detail = await screen.findByLabelText('Contract details')
  await waitFor(() => expect(within(detail).getByText(/≈ .* USD/)).toBeInTheDocument())
  expect(JSON.stringify(fixtures.secop)).toBe(stored)
})

test('Capital Markets price and authorized amount replace COP in their existing display elements', async () => {
  vi.spyOn(api, 'capitalMarkets').mockResolvedValue(fixtures.markets)
  vi.spyOn(api, 'securities').mockResolvedValue({
    items: [fixtures.instrument],
    total: 1,
    unfiltered_total: 1,
    page: 1,
    page_size: 10,
    has_more: false,
    availability: 'available',
  })
  const { container } = renderPresentation(<CapitalMarkets companyId={fixtures.id} />)
  await waitFor(() => expect(container.querySelector('.bvc-price')).toBeInTheDocument())
  const original = container.querySelector('.bvc-price')!.textContent
  await chooseOption(screen.getByRole('combobox', { name: 'Currency' }), 'USD')
  await waitFor(() => expect(container.querySelector('.bvc-price')).toHaveTextContent('≈ USD'))
  expect(container.querySelector('.bvc-price')).not.toHaveTextContent(original!.replace(/\s/g, ' '))
  expect(container.querySelector('.bvc-price strong')).toBeInTheDocument()
  expect(container.querySelector('.instruments-table td.numeric-cell')).toHaveTextContent('≈ USD')
})

test('manual exports keep original filters, include entered-on audit date and report bounds', async () => {
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async (input) =>
    String(input).includes('usd-rate')
      ? new Response(JSON.stringify(referenceRate))
      : new Response(JSON.stringify({ error: { message: 'limit', code: 'invalid_request' } }), {
          status: 413,
        }),
  )
  vi.stubGlobal('fetch', fetcher)
  renderPresentation()
  await chooseOption(screen.getByRole('combobox', { name: 'Currency' }), 'USD')
  await waitFor(() => expect(screen.getByLabelText('COP per USD')).toHaveValue('4000'))
  await userEvent.clear(screen.getByLabelText('COP per USD'))
  await userEvent.type(screen.getByLabelText('COP per USD'), '2000')
  await userEvent.click(screen.getByRole('button', { name: 'Export' }))
  await userEvent.click(screen.getByRole('button', { name: 'CSV' }))
  await screen.findByText(/Export exceeds 1,000 rows/)
  const call = fetcher.mock.calls.find(([input]) => String(input).includes('/exports/'))!
  const url = new URL(String(call[0]), 'http://test')
  expect(url.searchParams.get('q')).toBe('Árbol')
  expect(url.searchParams.get('raw_status')).toBe('En ejecución')
  expect(url.searchParams.get('run_id')).toBe('snapshot')
  expect(url.searchParams.has('page')).toBe(false)
  expect(url.searchParams.get('fx_mode')).toBe('manual')
  expect(url.searchParams.get('manual_rate')).toBe('2000')
  expect(url.searchParams.get('rate_date')).toBe(today)
})

test('one top export bar offers scopes and formats, supports Escape and outside dismissal', async () => {
  const user = userEvent.setup()
  renderPresentation()
  const toolbar = screen.getByLabelText('Export')
  const heading = screen.getByRole('heading', { name: 'Company' })
  expect(toolbar.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(screen.getAllByRole('button', { name: 'Export' })).toHaveLength(1)
  expect(screen.getByRole('combobox', { name: 'Export scope' })).toHaveValue('contracts')
  const trigger = screen.getByRole('button', { name: 'Export' })
  expect(screen.queryByRole('button', { name: 'CSV' })).not.toBeInTheDocument()
  await user.click(trigger)
  expect(trigger).toHaveAttribute('aria-expanded', 'true')
  expect(screen.getByRole('button', { name: 'CSV' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'JSON' })).toBeInTheDocument()
  await user.keyboard('{Escape}')
  expect(trigger).toHaveFocus()
  expect(trigger).toHaveAttribute('aria-expanded', 'false')
  await user.keyboard('{ArrowDown}')
  await waitFor(() => expect(screen.getByRole('button', { name: 'CSV' })).toHaveFocus())
  await user.click(heading)
  expect(screen.queryByRole('button', { name: 'CSV' })).not.toBeInTheDocument()
  await chooseOption(screen.getByRole('combobox', { name: 'Export scope' }), 'research')
  expect(screen.getByRole('combobox', { name: 'Export scope' })).toHaveValue('research')
})

test('top bar exports selected scope and latest contract filters without reusing them for research', async () => {
  const user = userEvent.setup()
  vi.spyOn(api, 'secop').mockResolvedValue(fixtures.secop)
  vi.spyOn(api, 'secopContracts').mockResolvedValue({
    items: fixtures.contracts.slice(0, 5),
    total: 7,
    page: 1,
    page_size: 5,
    has_more: true,
    run_id: fixtures.id,
  })
  const fetcher = vi.fn<typeof fetch>().mockImplementation(
    async () =>
      new Response(JSON.stringify({ error: { message: 'limit', code: 'invalid_request' } }), {
        status: 413,
      }),
  )
  vi.stubGlobal('fetch', fetcher)
  renderPresentation(<Screening companyId={fixtures.id} />)
  await screen.findByRole('columnheader', { name: 'Value (COP)' })
  await chooseOption(screen.getByRole('combobox', { name: 'Export scope' }), 'research')
  await user.click(screen.getByRole('button', { name: 'Export' }))
  await user.click(screen.getByRole('button', { name: 'JSON' }))
  await screen.findByText(/Export exceeds/)
  const research = new URL(String(fetcher.mock.calls[0]![0]), 'http://test')
  expect(research.pathname).toContain('/exports/research')
  expect(research.searchParams.has('run_id')).toBe(false)
  await user.type(screen.getByLabelText('Find contract'), 'Ñ')
  await chooseOption(screen.getByRole('combobox', { name: 'Export scope' }), 'contracts')
  await waitFor(() => expect(screen.getByRole('button', { name: 'Export' })).toBeEnabled())
  await user.click(screen.getByRole('button', { name: 'Export' }))
  await user.click(screen.getByRole('button', { name: 'CSV' }))
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2))
  const contracts = new URL(String(fetcher.mock.calls[1]![0]), 'http://test')
  expect(contracts.pathname).toContain('/exports/contracts')
  expect(contracts.searchParams.get('q')).toBe('Ñ')
  expect(contracts.searchParams.get('run_id')).toBe(fixtures.id)
  expect(contracts.searchParams.has('page')).toBe(false)
})
