import { useTranslation } from 'react-i18next'
import { changeLanguage, type Language } from '../i18n'

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation()
  return (
    <div className="language-switcher" role="group" aria-label={t('common.language')}>
      {(['en', 'es'] as const).map((language: Language) => (
        <button
          key={language}
          type="button"
          lang={language}
          aria-pressed={i18n.resolvedLanguage === language}
          aria-label={t(language === 'en' ? 'common.english' : 'common.spanish')}
          onClick={() => void changeLanguage(language)}
        >
          {language.toUpperCase()}
        </button>
      ))}
    </div>
  )
}
