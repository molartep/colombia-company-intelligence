export function RegistrationStatus({ status }: { status: string | null }) {
  const normalized = status?.trim().toUpperCase().replace(/\s+/g, ' ')
  const tone =
    normalized === 'ACTIVA'
      ? 'active'
      : normalized === 'CANCELADA'
        ? 'cancelled'
        : !normalized || normalized === 'NO ASIGNADO'
          ? 'unassigned'
          : 'other'

  return (
    <span className={`badge registration-status registration-status--${tone}`}>
      {status?.trim() || 'Missing from record'}
    </span>
  )
}
