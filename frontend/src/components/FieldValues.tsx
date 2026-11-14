import { dateTime, registrationDate, requiresTimestampReview } from '../utils'

export function MissingValue({ muted = false }: { muted?: boolean }) {
  return <span className={`badge value-pill--${muted ? 'muted' : 'missing'}`}>Missing</span>
}

export function ReviewValue({ value }: { value: string }) {
  return (
    <span className="badge value-pill--review" title={`Source value: ${value}`}>
      Review
    </span>
  )
}

export function RegistrationDate({
  value,
  blankIfMissing = false,
}: {
  value: string | null
  blankIfMissing?: boolean
}) {
  if (!value?.trim()) return blankIfMissing ? null : <MissingValue />
  const formatted = registrationDate(value)
  return formatted ? (
    <time dateTime={formatted.iso}>{formatted.display}</time>
  ) : (
    <ReviewValue value={value} />
  )
}

export function TimestampValue({ value, rues = false }: { value: string | null; rues?: boolean }) {
  if (!value?.trim()) return <MissingValue />
  if (!Number.isFinite(new Date(value).getTime()) || (rues && requiresTimestampReview(value))) {
    return <ReviewValue value={value} />
  }
  return <time dateTime={value}>{dateTime(value)}</time>
}
