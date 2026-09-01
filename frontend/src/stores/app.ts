import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import i18n, {
  getStoredLocale,
  LOCALE_STORAGE_KEY,
  type AppLocale,
} from '@/i18n'

/** 大屏模式默认缩放比例（1920×1080 下逻辑视口约 1280×720） */
const LS_DEFAULT_SCALE = 1.5
/** 大屏模式允许的最大缩放比例 */
const LS_MAX_SCALE = 3

/** 佈局配置 localStorage key */
const LAYOUT_CONFIG_KEY = '333-iot-layout-config'
/** 鎖定屏幕 localStorage key */
const LOCK_SCREEN_KEY = '333-iot-lock-screen'
/** 標籤頁 localStorage key */
const TABS_KEY = '333-iot-tabs'

export interface LayoutConfig {
  showTabs: boolean
  persistTabs: boolean
  showTabIcons: boolean
  tabStyle: 'card' | 'button'
  fixedHeader: boolean
  showLogo: boolean
  dynamicTitle: boolean
  showFooter: boolean
  sideTheme: 'dark' | 'light'
  themeMode: 'dark' | 'light'
  themeColor: string
}

const defaultLayoutConfig: LayoutConfig = {
  showTabs: true,
  persistTabs: true,
  showTabIcons: true,
  tabStyle: 'button',
  fixedHeader: true,
  showLogo: true,
  dynamicTitle: true,
  showFooter: true,
  sideTheme: 'dark',
  themeMode: 'light',
  themeColor: '#C4A574',
}

function getStoredLayoutConfig(): LayoutConfig {
  try {
    const raw = localStorage.getItem(LAYOUT_CONFIG_KEY)
    if (raw) return { ...defaultLayoutConfig, ...JSON.parse(raw) }
  } catch { /* ignore */ }
  return { ...defaultLayoutConfig }
}

export interface TabItem {
  key: string
  path: string
  /** 標籤標題：若為 i18n key（以 '.' 或已知前綴開頭），渲染時動態翻譯 */
  title: string
  /** i18n 翻譯 key，非空時優先於 title */
  titleKey?: string
  closable: boolean
}

function getStoredTabs(): TabItem[] {
  try {
    const raw = localStorage.getItem(TABS_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return []
}

function persistTabs(tabs: TabItem[]) {
  localStorage.setItem(TABS_KEY, JSON.stringify(tabs))
}

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(false)
  const locale = ref<AppLocale>(getStoredLocale())
  /** 是否处于大屏（iframe 嵌入）模式，由 URL 参数 ?ls=<scale> 激活 */
  const largeScreen = ref(false)
  /** 大屏模式整体缩放比例（zoom） */
  const lsScale = ref(1)
  /** 佈局配置 */
  const layoutConfig = ref<LayoutConfig>(getStoredLayoutConfig())
  /** 佈局設置抽屉是否開啟 */
  const layoutSettingsVisible = ref(false)
  /** 鎖定屏幕是否啟用（從 localStorage 持久化） */
  const lockScreenVisible = ref(localStorage.getItem(LOCK_SCREEN_KEY) === 'true')

  /** 標籤頁列表 */
  const tabs = ref<TabItem[]>(getStoredTabs())
  /** 當前激活的標籤頁 key */
  const activeTabKey = ref('')

  const hasTabs = computed(() => tabs.value.length > 0)

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
    const config = getStoredLayoutConfig()
    if (config.themeColor) {
      document.documentElement.style.setProperty('--brand-color', config.themeColor)
    }
  }

  function updateLayoutConfig(partial: Partial<LayoutConfig>) {
    layoutConfig.value = { ...layoutConfig.value, ...partial }
    localStorage.setItem(LAYOUT_CONFIG_KEY, JSON.stringify(layoutConfig.value))
    if (partial.themeColor) {
      document.documentElement.style.setProperty('--brand-color', partial.themeColor)
    }
  }

  function resetLayoutConfig() {
    layoutConfig.value = { ...defaultLayoutConfig }
    localStorage.setItem(LAYOUT_CONFIG_KEY, JSON.stringify(layoutConfig.value))
    document.documentElement.classList.remove('theme-dark', 'theme-light')
    document.documentElement.classList.add('theme-light')
    document.documentElement.style.setProperty('--brand-primary', defaultLayoutConfig.themeColor)
    document.documentElement.style.setProperty('--brand-color', defaultLayoutConfig.themeColor)
  }

  function openLayoutSettings() {
    layoutSettingsVisible.value = true
  }

  function closeLayoutSettings() {
    layoutSettingsVisible.value = false
  }

  function lockScreen() {
    lockScreenVisible.value = true
    localStorage.setItem(LOCK_SCREEN_KEY, 'true')
  }

  function unlockScreen() {
    lockScreenVisible.value = false
    localStorage.removeItem(LOCK_SCREEN_KEY)
  }

  /** 添加或切換標籤頁 */
  function addTab(tab: Omit<TabItem, 'closable'>) {
    const existing = tabs.value.find((t) => t.key === tab.key)
    if (!existing) {
      tabs.value.push({ ...tab, closable: tab.key !== '/' })
    } else {
      // 已存在時更新標題 / 標題 key，確保切換語言後標籤能同步
      if (tab.title) existing.title = tab.title
      if (tab.titleKey) existing.titleKey = tab.titleKey
    }
    activeTabKey.value = tab.key
    if (layoutConfig.value.persistTabs) {
      persistTabs(tabs.value)
    }
  }

  /** 關閉標籤頁，返回上一個 */
  function removeTab(key: string) {
    const idx = tabs.value.findIndex((t) => t.key === key)
    if (idx === -1) return
    const wasActive = tabs.value[idx].key === activeTabKey.value
    tabs.value.splice(idx, 1)
    if (wasActive && tabs.value.length > 0) {
      const newIdx = Math.min(idx, tabs.value.length - 1)
      activeTabKey.value = tabs.value[newIdx].key
      return tabs.value[newIdx].path
    }
    if (layoutConfig.value.persistTabs) {
      persistTabs(tabs.value)
    }
    return null
  }

  /** 關閉其他標籤頁 */
  function removeOtherTabs(key: string) {
    const target = tabs.value.find((t) => t.key === key)
    if (!target) return
    tabs.value = [target]
    activeTabKey.value = target.key
    if (layoutConfig.value.persistTabs) {
      persistTabs(tabs.value)
    }
  }

  /** 關閉左側標籤頁 */
  function removeLeftTabs(key: string) {
    const idx = tabs.value.findIndex((t) => t.key === key)
    if (idx <= 0) return
    const removed = tabs.value.splice(0, idx)
    if (removed.some((t) => t.key === activeTabKey.value)) {
      activeTabKey.value = key
    }
    if (layoutConfig.value.persistTabs) {
      persistTabs(tabs.value)
    }
  }

  /** 關閉右側標籤頁 */
  function removeRightTabs(key: string) {
    const idx = tabs.value.findIndex((t) => t.key === key)
    if (idx === -1 || idx >= tabs.value.length - 1) return
    const removed = tabs.value.splice(idx + 1)
    if (removed.some((t) => t.key === activeTabKey.value)) {
      activeTabKey.value = key
    }
    if (layoutConfig.value.persistTabs) {
      persistTabs(tabs.value)
    }
  }

  /** 關閉所有標籤頁 */
  function removeAllTabs() {
    const home = tabs.value.find((t) => t.key === '/')
    tabs.value = home ? [home] : []
    activeTabKey.value = home?.key || '/'
    if (layoutConfig.value.persistTabs) {
      persistTabs(tabs.value)
    }
    return home?.path || '/'
  }

  // 跨页面语言同步
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
    layoutConfig,
    layoutSettingsVisible,
    lockScreenVisible,
    tabs,
    activeTabKey,
    hasTabs,
    toggleSidebar,
    setLocale,
    initLocale,
    applyLargeScreenMode,
    updateLayoutConfig,
    resetLayoutConfig,
    openLayoutSettings,
    closeLayoutSettings,
    lockScreen,
    unlockScreen,
    addTab,
    removeTab,
    removeOtherTabs,
    removeLeftTabs,
    removeRightTabs,
    removeAllTabs,
  }
})
