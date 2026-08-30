import { defineStore } from 'pinia'
import { ref } from 'vue'
import i18n, {
  getStoredLocale,
  LOCALE_STORAGE_KEY,
  type AppLocale,
} from '@/i18n'

/** 大屏模式默认缩放比例（1920×1080 下逻辑视口约 1280×720） */
const LS_DEFAULT_SCALE = 1.5
/** 大屏模式允许的最大缩放比例 */
const LS_MAX_SCALE = 3

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(false)
  const locale = ref<AppLocale>(getStoredLocale())
  /** 是否处于大屏（iframe 嵌入）模式，由 URL 参数 ?ls=<scale> 激活 */
  const largeScreen = ref(false)
  /** 大屏模式整体缩放比例（zoom） */
  const lsScale = ref(1)

  /**
   * 解析 URL 参数 ?ls=<scale> 并应用大屏模式：
   * - 无 ls 参数 → 普通模式（不做缩放、不隐藏布局 chrome）
   * - ?ls=1.5 → 大屏模式，整页 zoom 放大 1.5 倍
   */
  function applyLargeScreenMode() {
    const raw = new URLSearchParams(window.location.search).get('ls')
    if (raw == null || raw === '') {
      largeScreen.value = false
      lsScale.value = 1
      document.documentElement.classList.remove('ls-on')
      document.documentElement.style.removeProperty('--ls-scale')
      return
    }
    const n = Number(raw)
    largeScreen.value = true
    lsScale.value = Number.isFinite(n) && n > 0 ? Math.min(n, LS_MAX_SCALE) : LS_DEFAULT_SCALE
    document.documentElement.classList.add('ls-on')
    document.documentElement.style.setProperty('--ls-scale', String(lsScale.value))
  }

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

  // 跨页面语言同步：PC 端切换语言后，大屏（?ls=）无需手动刷新即自动跟随
  window.addEventListener('storage', (e) => {
    if (e.key === LOCALE_STORAGE_KEY && e.newValue) {
      const v = e.newValue as AppLocale
      if (v === 'en' || v === 'zh-TW') setLocale(v)
    }
  })

  return {
    sidebarCollapsed,
    locale,
    largeScreen,
    lsScale,
    toggleSidebar,
    setLocale,
    initLocale,
    applyLargeScreenMode,
  }
})
