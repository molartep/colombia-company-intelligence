import { locale, t } from './index'

export function formatNumber(
  value: number | bigint | string,
  options: Intl.NumberFormatOptions = {},
) {
  // Intl accepts decimal strings as exact mathematical values. Never coerce to Number.
  return (
    new Intl.NumberFormat(locale(), options).format as (value: string | number | bigint) => string
  )(value)
}
function decimalScale(value: string): number | null {
  const match = /^[+-]?\d+(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/.exec(value)
  if (!match) return null
  return Math.max(0, (match[1]?.length ?? 0) - Number(match[2] ?? 0))
}
export function formatDecimal(value: string) {
  const fraction = decimalScale(value)
  // Intl supports up to 100 fraction digits. Preserve unusual source strings verbatim.
  if (fraction === null || fraction > 100) return value
  return formatNumber(value, {
    minimumFractionDigits: fraction,
    maximumFractionDigits: Math.max(fraction, 0),
  })
}
export function formatCurrency(value: string, currency: string) {
  const fraction = decimalScale(value)
  if (fraction === null || fraction > 100) return `${value} ${currency}`
  try {
    const defaults = new Intl.NumberFormat(locale(), {
      style: 'currency',
      currency,
    }).resolvedOptions()
    return formatNumber(value, {
      style: 'currency',
      currency,
      currencyDisplay: 'code',
      minimumFractionDigits: Math.max(fraction, defaults.minimumFractionDigits ?? 0),
      maximumFractionDigits: Math.max(fraction, defaults.maximumFractionDigits ?? 0),
    })
  } catch {
    return `${formatDecimal(value)} ${currency}`
  }
}
export function formatDate(value: string | null | undefined, withTime = false): string {
  if (!value) return t('format.notAvailable')
  const date = new Date(value.length === 10 ? `${value}T00:00:00Z` : value)
  if (
    !Number.isFinite(date.getTime()) ||
    (value.length === 10 && date.toISOString().slice(0, 10) !== value)
  )
    return value
  return new Intl.DateTimeFormat(locale(), {
    dateStyle: 'medium',
    ...(withTime ? { timeStyle: 'short' } : {}),
    timeZone: value.length === 10 ? 'UTC' : 'America/Bogota',
  }).format(date)
}
