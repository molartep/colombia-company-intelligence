export const dateTime = (value: string | null) =>
  value
    ? new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short' }).format(
        new Date(value),
      )
    : 'Not available'
export const label = (value: string) => value.replaceAll('_', ' ')
