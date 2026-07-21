import { createI18n } from 'vue-i18n'
import en from './locales/en'
import zhTW from './locales/zh-TW'

export type AppLocale = 'en' | 'zh-TW'

export const LOCALE_STORAGE_KEY = '333-iot-console-locale'

export function getStoredLocale(): AppLocale {
  const saved = localStorage.getItem(LOCALE_STORAGE_KEY)
  if (saved === 'en' || saved === 'zh-TW') return saved
  return 'en'
}

const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: getStoredLocale(),
  fallbackLocale: 'en',
  messages: {
    en,
    'zh-TW': zhTW,
  },
})

export default i18n
