import type { MarketsProfile, SecuritiesPage } from '../types/capitalMarkets'
import type { ParameterCatalog, Profile, RecordView, SearchPage } from '../types'

export async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal })
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null)
    const message =
      payload &&
      typeof payload === 'object' &&
      'error' in payload &&
      payload.error &&
      typeof payload.error === 'object' &&
      'message' in payload.error &&
      typeof payload.error.message === 'string'
        ? payload.error.message
        : `Request failed (${response.status}). Please try again.`
    throw new Error(message)
  }
  return response.json() as Promise<T>
}
export const api = {
  capitalMarkets: (id: string, signal?: AbortSignal, refresh = false, source?: string) =>
    request<MarketsProfile>(
      `/api/v1/companies/${encodeURIComponent(id)}/capital-markets${refresh ? `?refresh=true${source ? `&refresh_source=${encodeURIComponent(source)}` : ''}` : ''}`,
      signal,
    ),
  securities: (
    id: string,
    page: number,
    category: string,
    exchange: string,
    listingStatus: string,
    signal?: AbortSignal,
  ) => {
    const params = new URLSearchParams({ page: String(page), page_size: '10' })
    if (category) params.set('security_category', category)
    if (exchange) params.set('exchange', exchange)
    if (listingStatus) params.set('listing_status', listingStatus)
    return request<SecuritiesPage>(
      `/api/v1/companies/${encodeURIComponent(id)}/securities?${params}`,
      signal,
    )
  },
  parameters: (signal?: AbortSignal) => request<ParameterCatalog>('/api/v1/parameters', signal),
  search: (q: string, page: number, signal?: AbortSignal, filters = '') =>
    request<SearchPage>(
      `/api/v1/companies?${new URLSearchParams({ q, page: String(page), page_size: '20' })}${filters ? `&${filters}` : ''}`,
      signal,
    ),
  profile: (id: string, signal?: AbortSignal, refresh = false) =>
    request<Profile>(
      `/api/v1/companies/${encodeURIComponent(id)}${refresh ? '?refresh=true' : ''}`,
      signal,
    ),
  sources: (id: string, signal?: AbortSignal) =>
    request<RecordView[]>(`/api/v1/companies/${encodeURIComponent(id)}/sources`, signal),
}
