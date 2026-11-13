import type { Profile, RecordView, SearchPage } from '../types'

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
  search: (q: string, page: number, signal?: AbortSignal) =>
    request<SearchPage>(
      `/api/v1/companies?${new URLSearchParams({ q, page: String(page), page_size: '20' })}`,
      signal,
    ),
  profile: (id: string, signal?: AbortSignal) =>
    request<Profile>(`/api/v1/companies/${encodeURIComponent(id)}`, signal),
  sources: (id: string, signal?: AbortSignal) =>
    request<RecordView[]>(`/api/v1/companies/${encodeURIComponent(id)}/sources`, signal),
}
