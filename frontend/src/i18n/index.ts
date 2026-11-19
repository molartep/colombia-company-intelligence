import i18n from 'i18next'
import { initReactI18next, useTranslation } from 'react-i18next'
import en from './locales/en.json'
import es from './locales/es.json'

export type Language = 'en' | 'es'
export const LANGUAGE_STORAGE_KEY = 'cci.language'
export function detectLanguage(
  storage?: Pick<Storage, 'getItem'>,
  preferences: readonly string[] = navigator.languages,
): Language {
  try {
    const saved = storage?.getItem(LANGUAGE_STORAGE_KEY)
    if (saved === 'en' || saved === 'es') return saved
  } catch {
    /* Storage can be unavailable in private or embedded contexts. */
  }
  for (const value of preferences) {
    const language = value.toLowerCase().split('-')[0]
    if (language === 'en' || language === 'es') return language
  }
  return 'es'
}
let storage: Storage | undefined
try {
  storage = window.localStorage
} catch {
  /* Use browser preferences. */
}
void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, es: { translation: es } },
  lng: detectLanguage(storage),
  fallbackLng: 'es',
  supportedLngs: ['en', 'es'],
  initAsync: false,
  interpolation: { escapeValue: false, alwaysFormat: true },
  returnEmptyString: false,
  react: { useSuspense: false },
})
const formatter = i18n.services.formatter
if (formatter) {
  const original = formatter.format.bind(formatter)
  formatter.format = (value, format, language, options) => {
    if (typeof value === 'number' && !format)
      return new Intl.NumberFormat(language === 'en' ? 'en-US' : 'es-CO').format(value)
    return format ? original(value, format, language, options) : String(value)
  }
}
function updateDocument(language: string) {
  document.documentElement.lang = language
  document
    .querySelector('meta[name="description"]')
    ?.setAttribute('content', i18n.t('application.description'))
}
i18n.on('languageChanged', updateDocument)
updateDocument(i18n.resolvedLanguage ?? 'es')
export async function changeLanguage(language: Language) {
  try {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language)
  } catch {
    /* Switching still works without persistence. */
  }
  await i18n.changeLanguage(language)
}
export function useLanguage() {
  useTranslation()
  return locale()
}
export function locale() {
  return i18n.resolvedLanguage === 'en' ? 'en-US' : 'es-CO'
}
export const t = i18n.t.bind(i18n)
export default i18n
