import { t } from './index'
import messageKeys from './messageKeys.json'

// Only use for known application-generated API prose. Never pass source values here.
export function uiMessage(value: string | null | undefined): string {
  if (!value) return ''
  const key = (messageKeys as Record<string, string>)[value]
  if (key) return t(key)
  const excluded =
    /^Se excluyeron (\d+) filas o contratos ambiguos de los resultados verificados\.$/.exec(value)
  if (excluded) return t('messages.secop.excluded', { count: Number(excluded[1]) })
  const review = /^Revisar valor original de fuente: (.*)$/.exec(value)
  if (review) return t('messages.capital.review', { field: review[1] })
  const outage = /^(.*): official source failed; showing previously retrieved records\.$/.exec(
    value,
  )
  if (outage) return t('messages.rues.outage', { source: outage[1] })
  // Unrecognized data stays untouched instead of accidentally translating external evidence.
  return value
}
export function errorMessage(error: Error): string {
  if ('code' in error && typeof error.code === 'string') {
    const code = error.code
    if (
      [
        'source_timeout',
        'source_rate_limited',
        'source_request_failed',
        'source_schema_changed',
        'source_invalid_response',
      ].includes(code)
    )
      return t('errors.source_unavailable')
    return t(`errors.${code}`, { defaultValue: t('errors.generic') })
  }
  if (error instanceof TypeError) return t('errors.network')
  const key = (messageKeys as Record<string, string>)[error.message]
  return key ? t(key) : t('errors.generic')
}
