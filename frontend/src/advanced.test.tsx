import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { Advanced } from './pages/Advanced'
import { Search } from './pages/Search'
import { DirectoryImport } from './components/DirectoryImport'

const snapshot = {
  checked_at: '2026-11-18T15:00:00Z',
  counts: { issuers: 0, registrations: 2, snapshots: 0 },
  directory_missing: true,
  import_access: 'local',
  parameter_verified_at: '2026-11-14T15:00:00Z',
  parameter_options: 25,
  rues: {
    name: 'RUES',
    dataset_url: 'https://www.datos.gov.co/d/c82u-588k',
    availability: 'available',
    last_checked_at: '2026-11-18T14:00:00Z',
    last_updated_at: null,
  },
  sources: [
    {
      id: 'sfc_rnve',
      name: 'RNVE issuer directory',
      source_url: 'https://www.superfinanciera.gov.co/',
      availability: 'not_yet_checked',
      last_ingestion_status: 'not_yet_checked',
      last_attempt_at: null,
      last_success_at: null,
      latest_snapshot: null,
      stale: true,
    },
  ],
}
const imported = { record_count: 307, snapshot_id: 'synthetic-snapshot', complete_current: false }
function response(data: unknown, status = 200) {
  return { ok: status === 200, status, json: async () => data }
}
function wrapper(node: React.ReactNode, path = '/') {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[path]}>{node}</MemoryRouter>
    </QueryClientProvider>,
  )
}
afterEach(() => vi.unstubAllGlobals())

test('XLSX fallback posts the selected file and clears the administrator key after success', async () => {
  const file = new File(['synthetic workbook bytes'], 'Emisores.xlsx')
  const fetcher = vi.fn(async (_url: string, init?: RequestInit) => {
    expect(init?.method).toBe('POST')
    expect(init?.body).toBe(file)
    expect(init?.headers).toMatchObject({
      'X-CCI-Admin-Token': 'synthetic-administrator-key-for-test',
    })
    return response(imported)
  })
  vi.stubGlobal('fetch', fetcher)
  wrapper(<DirectoryImport />)
  await userEvent.click(screen.getByText('Import a downloaded XLSX / administrator access'))
  await userEvent.type(
    screen.getByLabelText(/Administrator import key/),
    'synthetic-administrator-key-for-test',
  )
  await userEvent.upload(screen.getByLabelText(/Official issuer XLSX/), file)
  await userEvent.click(screen.getByRole('button', { name: 'Import selected XLSX' }))
  expect(await screen.findByText(/Imported 307 issuers/)).toBeVisible()
  expect(screen.getByLabelText(/Administrator import key/)).toHaveValue('')
  expect(fetcher.mock.calls[0]?.[0]).toContain('method=upload')
})

test('Advanced shows actual empty dependencies separately from on-demand sources and architecture', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => response(snapshot)),
  )
  wrapper(<Advanced />)
  expect(await screen.findByText('RNVE directory is empty.')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Import RNVE directory' })).toBeVisible()
  expect(screen.getByRole('heading', { name: 'Architecture' })).toBeVisible()
  expect(screen.getByText(/not live upstream probes/)).toBeVisible()
  expect(screen.getByText(/No initial data import/i)).toBeVisible()
  expect(screen.getByText(/6. Runtime boundaries/)).toBeVisible()
})

test('missing-directory search alert executes import then retries the blocked search', async () => {
  let ready = false
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.includes('/admin/imports/rnve')) {
      expect(init?.method).toBe('POST')
      ready = true
      return response(imported)
    }
    return ready
      ? response({
          items: [],
          page: 1,
          page_size: 20,
          has_more: false,
          stale: false,
          warning: null,
        })
      : response(
          {
            error: {
              code: 'bvc_directory_unavailable',
              message: 'Import the official RNVE issuer directory before using Registrado BVC.',
            },
          },
          503,
        )
  })
  vi.stubGlobal('fetch', fetcher)
  wrapper(<Search />, '/?q=SYNTHETIC&registered_bvc=true')
  await userEvent.click(await screen.findByRole('button', { name: 'Import RNVE directory' }))
  expect(await screen.findByText('No matching registrations')).toBeVisible()
  expect(fetcher.mock.calls.filter(([url]) => url.includes('/admin/imports/rnve'))).toHaveLength(1)
  expect(fetcher.mock.calls.filter(([url]) => url.includes('/companies?'))).toHaveLength(2)
})

test('invalid uploads are rejected locally and failed import preserves the retry action', async () => {
  const fetcher = vi.fn(async () =>
    response(
      {
        error: {
          code: 'rnve_download_failed',
          message: 'Download failed; upload the official export.',
        },
      },
      503,
    ),
  )
  vi.stubGlobal('fetch', fetcher)
  wrapper(<DirectoryImport />)
  await userEvent.click(screen.getByText('Import a downloaded XLSX / administrator access'))
  await userEvent.upload(
    screen.getByLabelText(/Official issuer XLSX/),
    new File(['not an xlsx'], 'wrong.txt'),
    { applyAccept: false },
  )
  expect(await screen.findByText('Choose an XLSX file no larger than 10 MiB.')).toBeVisible()
  expect(fetcher).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: 'Import RNVE directory' }))
  expect(await screen.findByText('Download failed; upload the official export.')).toBeVisible()
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Import RNVE directory' })).toBeEnabled(),
  )
})
