import { defineStore } from 'pinia'
import { ref } from 'vue'
import i18n, {
  getStoredLocale,
  LOCALE_STORAGE_KEY,
  type AppLocale,
} from '@/i18n'

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(false)
  const locale = ref<AppLocale>(getStoredLocale())

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function setLocale(next: AppLocale) {
    locale.value = next
    i18n.global.locale.value = next
    localStorage.setItem(LOCALE_STORAGE_KEY, next)
    document.documentElement.lang = next === 'zh-TW' ? 'zh-HK' : 'en'
  }

  function initLocale() {
    setLocale(locale.value)
  }

  return { sidebarCollapsed, locale, toggleSidebar, setLocale, initLocale }
})
