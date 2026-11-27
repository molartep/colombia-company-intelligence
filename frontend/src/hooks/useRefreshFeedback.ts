import { useEffect, useState } from 'react'
import { ApiError } from '../api/client'
import { t } from '../i18n'

/** Server retry windows apply to refresh actions, not source evidence. */
export function useRefreshFeedback() {
  const [now, setNow] = useState(Date.now)
  const [deadline, setDeadline] = useState(0)
  useEffect(() => {
    if (!deadline || deadline <= Date.now()) return
    const interval = window.setInterval(() => {
      const current = Date.now()
      setNow(current)
      if (current >= deadline) window.clearInterval(interval)
    }, 1000)
    return () => window.clearInterval(interval)
  }, [deadline])
  return {
    seconds: Math.max(0, Math.ceil((deadline - now) / 1000)),
    onError(error: Error) {
      if (error instanceof ApiError && error.status === 429) {
        const current = Date.now()
        setNow(current)
        setDeadline(current + (error.retryAfterSeconds ?? 60) * 1000)
      }
    },
    message(error: Error | null) {
      if (error instanceof ApiError && error.status === 403)
        return t('errors.refresh_origin_forbidden')
      if (error instanceof ApiError && error.status === 429) return t('errors.refresh_cooldown')
      return null
    },
  }
}
