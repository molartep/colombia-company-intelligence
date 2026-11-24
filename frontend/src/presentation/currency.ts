export interface Rate {
  cop_per_usd: string
  source: string
  source_url: string | null
  effective_date: string
  effective_until: string
  retrieved_at: string
  manual: boolean
  stale: boolean
  provider_failed: boolean
}
export const validRate = (value: string) =>
  /^\d{1,12}(?:\.\d{1,12})?$/.test(value) && /[1-9]/.test(value)

// Exact integer division with round-half-even cents, matching backend Decimal.
export function toUsd(amount: string, rate: string): string | null {
  if (!validRate(rate) || !/^-?\d+(?:\.\d+)?$/.test(amount)) return null
  const negative = amount.startsWith('-')
  const [whole, fraction = ''] = amount.replace(/^-/, '').split('.')
  const [rw, rf = ''] = rate.split('.')
  const numerator = BigInt(whole + fraction) * 10n ** BigInt(rf.length) * 100n
  const denominator = BigInt(rw + rf) * 10n ** BigInt(fraction.length)
  let cents = numerator / denominator
  const remainder = numerator % denominator
  if (remainder * 2n > denominator || (remainder * 2n === denominator && cents % 2n === 1n))
    cents += 1n
  const digits = cents.toString().padStart(3, '0')
  return `${negative && cents !== 0n ? '-' : ''}${digits.slice(0, -2)}.${digits.slice(-2)}`
}
