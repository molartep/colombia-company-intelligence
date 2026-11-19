import { t, useLanguage } from '../i18n'
export function SearchButton({ disabled = false }: { disabled?: boolean }) {
  useLanguage()

  return (
    <button className="search-submit" type="submit" disabled={disabled}>
      {' '}
      {t('search.search')} <span aria-hidden="true">↗</span>
    </button>
  )
}
