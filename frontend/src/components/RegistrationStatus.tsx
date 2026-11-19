import { t, useLanguage } from '../i18n'
export function RegistrationStatus({ status }: { status: string | null }) {
  useLanguage()

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
      {status || t('registration.missingFromRecord')}
    </span>
  )
}
