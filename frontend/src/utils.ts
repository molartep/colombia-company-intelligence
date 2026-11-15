export const dateTime = (value: string | null) =>
  value
    ? new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short' }).format(
        new Date(value),
      )
    : 'Not available'
export const label = (value: string) => value.replaceAll('_', ' ')

export function registrationDate(value: string): { iso: string; display: string } | null {
  const raw = value.trim()
  const pattern = raw.length === 8 ? /^(\d{4})(\d{2})(\d{2})$/ : /^(\d{4})-(\d{2})-(\d{2})$/
  const match = pattern.exec(raw)
  if (!match) return null
  const iso = `${match[1]}-${match[2]}-${match[3]}`
  // Treat source placeholders and impossible calendar dates as reviewable evidence.
  if (raw === '00000000' || match[1] === '0000' || match[1] === '9999') return null
  const date = new Date(`${iso}T00:00:00Z`)
  if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== iso) return null
  return {
    iso,
    display: new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeZone: 'UTC' }).format(date),
  }
}

export function requiresTimestampReview(value: string): boolean {
  // RUES's 1900-01-01 sentinel survives conversion from Colombia time into UTC.
  // Check the encoded source date so the flag does not depend on the viewer's timezone.
  return value.trim().startsWith('1900-01-01')
}

export function searchReturnPath(state: unknown): string {
  if (
    state &&
    typeof state === 'object' &&
    'returnTo' in state &&
    typeof state.returnTo === 'string'
  ) {
    // Navigation state may only restore this app's search route.
    if (state.returnTo === '/' || state.returnTo.startsWith('/?')) return state.returnTo
  }
  return '/'
}

export function issuanceMonth(value: string | null): string {
  if (!value) return 'No informada'
  const match = /^(\d{4})(0[1-9]|1[0-2])$/.exec(value)
  if (!match || Number(match[1]) === 0) return value
  const months = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ]
  return `${months[Number(match[2]) - 1]}, ${match[1]}`
}
