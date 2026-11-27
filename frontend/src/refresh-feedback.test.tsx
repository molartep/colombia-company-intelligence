import { act, renderHook } from '@testing-library/react'
import { ApiError, request } from './api/client'
import { useRefreshFeedback } from './hooks/useRefreshFeedback'
import { changeLanguage } from './i18n'

beforeEach(async () => {
  await changeLanguage('en')
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

test('refresh follows the server retry window and re-enables afterward', () => {
  vi.useFakeTimers()
  const hook = renderHook(() => useRefreshFeedback())
  act(() => hook.result.current.onError(new ApiError('Wait', 'invalid_request', 429, 2)))
  expect(hook.result.current.seconds).toBe(2)
  act(() => {
    vi.advanceTimersByTime(1000)
  })
  expect(hook.result.current.seconds).toBe(1)
  act(() => {
    vi.advanceTimersByTime(1000)
  })
  expect(hook.result.current.seconds).toBe(0)
  hook.unmount()
  expect(vi.getTimerCount()).toBe(0)
})

test('origin rejection explains the app configuration problem', () => {
  const { result } = renderHook(() => useRefreshFeedback())
  expect(result.current.message(new ApiError('Denied', 'invalid_request', 403))).toContain(
    'configured frontend origin',
  )
  expect(result.current.message(new Error('other'))).toBeNull()
})

test('the API client retains Retry-After without exposing raw server error prose', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: { code: 'invalid_request', message: 'Wait' } }), {
        status: 429,
        headers: { 'Retry-After': '7' },
      }),
    ),
  )
  await expect(request('/refresh')).rejects.toMatchObject({ status: 429, retryAfterSeconds: 7 })
})
