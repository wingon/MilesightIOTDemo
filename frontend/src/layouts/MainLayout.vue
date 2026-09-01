<script setup lang="ts">
import { computed, h, ref, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import * as Icons from '@ant-design/icons-vue'
import {
  GlobalOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  UserOutlined,
  SettingOutlined,
  LockOutlined,
  ProfileOutlined,
  CloseOutlined,
  HomeOutlined,
} from '@ant-design/icons-vue'
import type { ItemType } from 'ant-design-vue'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'
import { usePermissionStore } from '@/stores/permission'
import type { MenuNode } from '@/api/auth'
import type { AppLocale } from '@/i18n'
import LayoutSettings from '@/components/LayoutSettings.vue'
import LockScreen from '@/components/LockScreen.vue'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const userStore = useUserStore()
const permissionStore = usePermissionStore()

const {
  layoutConfig,
  sidebarCollapsed,
  largeScreen,
  tabs,
  activeTabKey,
  lockScreenVisible,
} = storeToRefs(appStore)

const selectedKeys = computed(() => {
  const p = route.path
  if (p.startsWith('/building-viewer/floor/')) return ['/building-viewer']
  return [p === '/' ? '/' : p]
})

const brandLine1 = computed(() => String(t('common.brandLine1')))
const brandLine2 = computed(() => String(t('common.brandLine2')))

const menuItems = computed<ItemType[]>(() => buildMenuItems(permissionStore.menuTree))

function buildMenuItems(menus: MenuNode[]): ItemType[] {
  return menus
    .filter((m) => m.menu_type !== 'F')
    .map((m) => {
      const children = m.children?.length ? buildMenuItems(m.children) : undefined
      return {
        key: menuKey(m),
        icon: m.icon
          ? () =>
              h(
                (Icons as unknown as Record<string, typeof UserOutlined>)[m.icon!] ||
                  Icons.AppstoreOutlined,
              )
          : undefined,
        label: m.i18n_key ? t(m.i18n_key) : m.menu_name,
        children,
      } as ItemType
    })
}

function menuKey(m: MenuNode): string {
  if (!m.path) return `dir-${m.id}`
  if (m.path === '/') return '/'
  return m.path.startsWith('/') ? m.path : `/${m.path}`
}

const pageTitle = computed(() => {
  const key = route.meta.titleKey as string | undefined
  return key ? t(key) : t('common.brand')
})

watch(pageTitle, (title) => {
  if (layoutConfig.value.dynamicTitle) {
    document.title = `${title} · ${t('common.brand')}`
  } else {
    document.title = t('common.brand')
  }
})

const localeOptions = computed(() => [
  { value: 'en', label: t('common.english') },
  { value: 'zh-TW', label: t('common.zhTw') },
])

const mainOffset = computed(() => (sidebarCollapsed.value ? '80px' : '240px'))

const displayName = computed(
  () => userStore.userInfo?.nickname || userStore.userInfo?.username || '',
)

const activeTabIndex = computed(() =>
  tabs.value.findIndex((tab) => tab.key === activeTabKey.value),
)

/** 標籤顯示標題：優先 titleKey 動態翻譯，其次存儲的 title */
const tabTitles = computed<Record<string, string>>(() => {
  const map: Record<string, string> = {}
  for (const tab of tabs.value) {
    map[tab.key] = tab.titleKey ? t(tab.titleKey) : tab.title
  }
  return map
})

/** 右鍵菜單項（刷新 / 關閉當前 / 關閉其他 / 關閉左側 / 關閉右側 / 全部關閉） */
const tabMenuItems = computed(() => [
  { key: 'refresh', label: t('tabs.refresh') },
  { key: 'closeCurrent', label: t('tabs.closeCurrent') },
  { key: 'closeOthers', label: t('tabs.closeOthers') },
  { key: 'closeLeft', label: t('tabs.closeLeft') },
  { key: 'closeRight', label: t('tabs.closeRight') },
  { type: 'divider' as const, key: 'divider' },
  { key: 'closeAll', label: t('tabs.closeAll') },
])

watch(
  () => route.path,
  (path) => {
    const key = path === '/' ? '/' : path
    const titleKey = route.meta?.titleKey as string | undefined
    const title = titleKey ? t(titleKey) : (pageTitle.value || path)
    appStore.addTab({ key, path, title, titleKey })
    activeTabKey.value = key
  },
  { immediate: true },
)

function onMenuClick(info: { key: string | number }) {
  const key = String(info.key)
  if (key.startsWith('/')) router.push(key)
}

function onLocaleChange(value: unknown) {
  appStore.setLocale(value as AppLocale)
  const key = route.meta.titleKey as string | undefined
  const title = key ? t(key) : t('common.brand')
  if (layoutConfig.value.dynamicTitle) {
    document.title = `${title} · ${t('common.brand')}`
  } else {
    document.title = t('common.brand')
  }
}

async function onLogout() {
  await userStore.logout()
  permissionStore.reset()
  router.push('/login')
}

function handleUserMenuClick(key: string) {
  switch (key) {
    case 'profile':
      router.push('/profile')
      break
    case 'layoutSettings':
      appStore.openLayoutSettings()
      break
    case 'lockScreen':
      appStore.lockScreen()
      break
    case 'logout':
      onLogout()
      break
  }
}

function onTabClick(key: string) {
  const tab = tabs.value.find((t) => t.key === key)
  if (tab) {
    activeTabKey.value = key
    router.push(tab.path)
  }
}

function onTabClose(key: string) {
  const homeKey = '/'
  if (key === homeKey) return
  const targetPath = appStore.removeTab(key)
  if (targetPath) {
    router.push(targetPath)
  } else if (activeTabKey.value) {
    const tab = tabs.value.find((t) => t.key === activeTabKey.value)
    if (tab) router.push(tab.path)
  }
}

function onTabCloseOthers() {
  appStore.removeOtherTabs(activeTabKey.value)
}

function onTabCloseAll() {
  const homePath = appStore.removeAllTabs()
  router.push(homePath)
}

/** ═══ 標籤右鍵菜單 ═══ */
const tabMenuVisible = ref(false)
const tabMenuX = ref(0)
const tabMenuY = ref(0)
const tabMenuKey = ref('')

function onTabContextMenu(e: MouseEvent, key: string) {
  e.preventDefault()
  tabMenuKey.value = key
  tabMenuX.value = e.clientX
  tabMenuY.value = e.clientY
  tabMenuVisible.value = true
}

function closeTabMenu() {
  tabMenuVisible.value = false
}

function onTabMenuRefresh() {
  const tab = tabs.value.find((t) => t.key === tabMenuKey.value)
  closeTabMenu()
  if (!tab) return
  const current = route.path
  if (tab.key === current) {
    // 刷新当前页：reload 前先移除当前 tab 避免重复添加
    router.replace({ path: '/redirect' + current }).then(() => {
      router.replace(current)
    })
  } else {
    router.push(tab.path)
  }
}

function onTabMenuCloseCurrent() {
  const key = tabMenuKey.value
  closeTabMenu()
  onTabClose(key)
}

function onTabMenuCloseOthers() {
  appStore.removeOtherTabs(tabMenuKey.value)
  closeTabMenu()
}

function onTabMenuCloseLeft() {
  appStore.removeLeftTabs(tabMenuKey.value)
  closeTabMenu()
}

function onTabMenuCloseRight() {
  appStore.removeRightTabs(tabMenuKey.value)
  closeTabMenu()
}

function onTabMenuCloseAll() {
  const homePath = appStore.removeAllTabs()
  closeTabMenu()
  router.push(homePath)
}

function onTabMenuAction(key: string) {
  switch (key) {
    case 'refresh':
      onTabMenuRefresh()
      break
    case 'closeCurrent':
      onTabMenuCloseCurrent()
      break
    case 'closeOthers':
      onTabMenuCloseOthers()
      break
    case 'closeLeft':
      onTabMenuCloseLeft()
      break
    case 'closeRight':
      onTabMenuCloseRight()
      break
    case 'closeAll':
      onTabMenuCloseAll()
      break
  }
}

/** 點擊菜單外區域關閉右鍵菜單 */
function onGlobalClick() {
  if (tabMenuVisible.value) tabMenuVisible.value = false
}

onMounted(() => {
  window.addEventListener('click', onGlobalClick)
  window.addEventListener('resize', onGlobalClick)
  window.addEventListener('scroll', onGlobalClick, true)
})

onUnmounted(() => {
  window.removeEventListener('click', onGlobalClick)
  window.removeEventListener('resize', onGlobalClick)
  window.removeEventListener('scroll', onGlobalClick, true)
})
</script>

<template>
  <a-layout class="shell" :class="{ 'ls-shell': largeScreen }">
    <a-layout-sider
      v-if="!largeScreen"
      collapsible
      :collapsed="sidebarCollapsed"
      :trigger="null"
      width="240"
      :collapsed-width="80"
      :theme="layoutConfig.sideTheme === 'light' ? 'light' : 'dark'"
      class="sider"
      :class="{ 'sider-light': layoutConfig.sideTheme === 'light' }"
    >
      <div v-if="layoutConfig.showLogo" class="brand" :class="{ collapsed: sidebarCollapsed }">
        <img class="brand-logo" src="/wingon-logo.png" alt="Wing On" />
        <div v-if="!sidebarCollapsed" class="brand-text">
          <div class="brand-name">
            <span class="brand-line1">{{ brandLine1 }}</span>
            <span class="brand-line2">{{ brandLine2 }}</span>
          </div>
        </div>
      </div>
      <a-menu
        :theme="layoutConfig.sideTheme === 'light' ? 'light' : 'dark'"
        mode="inline"
        :selected-keys="selectedKeys"
        :items="menuItems"
        @click="onMenuClick"
      />
    </a-layout-sider>

    <a-layout
      class="main"
      :class="{ 'ls-main': largeScreen }"
      :style="largeScreen ? undefined : { marginLeft: mainOffset }"
    >
      <a-layout-header
        v-if="!largeScreen"
        class="header"
        :class="{ 'header-fixed': layoutConfig.fixedHeader, 'header-static': !layoutConfig.fixedHeader }"
      >
        <a-button type="text" class="trigger" @click="appStore.toggleSidebar">
          <MenuUnfoldOutlined v-if="sidebarCollapsed" />
          <MenuFoldOutlined v-else />
        </a-button>
        <div class="header-main">
          <div class="header-title">{{ pageTitle }}</div>
        </div>
        <div class="header-right">
          <GlobalOutlined class="lang-icon" />
          <a-select
            :value="locale"
            :options="localeOptions"
            style="width: 140px"
            :aria-label="t('common.language')"
            @change="onLocaleChange"
          />
          <a-dropdown>
            <div class="user-chip">
              <UserOutlined class="user-icon" />
              <span class="user-name">{{ displayName }}</span>
            </div>
            <template #overlay>
              <a-menu @click="({ key }: { key: string | number }) => handleUserMenuClick(String(key))">
                <a-menu-item key="profile">
                  <ProfileOutlined />
                  {{ t('common.profile') }}
                </a-menu-item>
                <a-menu-item key="layoutSettings">
                  <SettingOutlined />
                  {{ t('common.layoutSettings') }}
                </a-menu-item>
                <a-menu-item key="lockScreen">
                  <LockOutlined />
                  {{ t('common.lockScreen') }}
                </a-menu-item>
                <a-menu-divider />
                <a-menu-item key="logout">
                  <LogoutOutlined />
                  {{ t('common.logout') }}
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
      </a-layout-header>

      <!-- 標籤頁欄 -->
      <div
        v-if="layoutConfig.showTabs && !largeScreen && tabs.length > 0"
        class="tabs-bar"
        :class="`tabs-${layoutConfig.tabStyle}`"
      >
        <div
          v-for="(tab, idx) in tabs"
          :key="tab.key"
          class="tab-item"
          :class="{ active: tab.key === activeTabKey }"
          @click="onTabClick(tab.key)"
          @contextmenu="(e) => onTabContextMenu(e, tab.key)"
        >
          <HomeOutlined v-if="tab.key === '/' && layoutConfig.showTabIcons" class="tab-icon" />
          <span class="tab-title">{{ tabTitles[tab.key] }}</span>
          <CloseOutlined
            v-if="tab.closable"
            class="tab-close"
            @click.stop="onTabClose(tab.key)"
          />
        </div>
      </div>

      <!-- 標籤右鍵菜單 -->
      <teleport to="body">
        <div
          v-if="tabMenuVisible"
          class="tab-context-menu"
          :style="{ left: tabMenuX + 'px', top: tabMenuY + 'px' }"
          @click.stop
        >
          <a-menu
            :items="tabMenuItems"
            :selected-keys="[]"
            @click="(info: { key: string | number }) => onTabMenuAction(String(info.key))"
          />
        </div>
      </teleport>

      <a-layout-content class="content" :class="{ 'ls-content': largeScreen }">
        <router-view />
      </a-layout-content>

      <a-layout-footer v-if="layoutConfig.showFooter && !largeScreen" class="footer">
        Copyright © 2018-2026 Wing On. All Rights Reserved.
      </a-layout-footer>
    </a-layout>
  </a-layout>

  <LayoutSettings />
  <LockScreen v-if="lockScreenVisible" />
</template>

<style scoped lang="less">
.shell {
  min-height: 100vh;
  background: var(--brand-canvas, #f7f7f5);
  transition: background 0.3s;
}

.shell.ls-shell {
  min-height: calc(100vh / var(--ls-scale, 1));
}

.sider {
  position: fixed !important;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 99;
  height: 100vh !important;
  overflow-y: auto;
  background: #1a1a1a !important;
  border-right: 1px solid rgba(196, 165, 116, 0.25);

  :deep(.ant-layout-sider-children) {
    background: #1a1a1a;
  }

  :deep(.ant-menu-dark) {
    background: #1a1a1a;
  }

  :deep(.ant-menu-dark .ant-menu-item) {
    transition: background 0.18s ease, color 0.18s ease;
  }

  :deep(.ant-menu-dark .ant-menu-item:hover) {
    background: rgba(196, 165, 116, 0.14) !important;
    color: #f5ead7 !important;
  }

  :deep(.ant-menu-dark .ant-menu-item:hover .anticon) {
    color: #f5ead7 !important;
  }

  :deep(.ant-menu-dark .ant-menu-item-selected) {
    background: #c4a574 !important;
    color: #0d0d0d !important;
    font-weight: 600;
    box-shadow: inset 3px 0 0 #0d0d0d;
  }

  :deep(.ant-menu-dark .ant-menu-item-selected .anticon) {
    color: #0d0d0d !important;
  }

  :deep(.ant-menu-dark .ant-menu-submenu-title:hover) {
    color: #f5ead7 !important;
  }

  :deep(.ant-layout-sider-children)::-webkit-scrollbar,
  .sider::-webkit-scrollbar {
    width: 6px;
  }

  :deep(.ant-layout-sider-children)::-webkit-scrollbar-thumb,
  .sider::-webkit-scrollbar-thumb {
    background: rgba(196, 165, 116, 0.35);
    border-radius: 3px;
  }

  :deep(.ant-layout-sider-children)::-webkit-scrollbar-track,
  .sider::-webkit-scrollbar-track {
    background: transparent;
  }
}

.sider-light {
  background: #ffffff !important;
  border-right: 1px solid #e6e2da;

  :deep(.ant-layout-sider-children) {
    background: #ffffff;
  }

  :deep(.ant-menu-light) {
    background: #ffffff;
  }

  :deep(.ant-menu-light .ant-menu-item-selected) {
    background: #f2efe9 !important;
    color: var(--brand-color, #c4a574) !important;
    font-weight: 600;
  }

  :deep(.ant-menu-light .ant-menu-item:hover) {
    background: #f7f7f5 !important;
  }
}

.main {
  min-height: calc(100vh / var(--ls-scale, 1));
  transition: margin-left 0.2s;
}

.brand {
  min-height: 72px;
  margin: 0 12px;
  padding: 12px 4px;
  display: flex;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid rgba(196, 165, 116, 0.28);

  &.collapsed {
    justify-content: center;
  }
}

.brand-logo {
  width: 54px;
  height: auto;
  object-fit: contain;
  flex-shrink: 0;
  filter: brightness(1.05);
}

.brand-text {
  min-width: 0;
  flex: 1;
}

.brand-name {
  color: #c4a574;
  font-weight: 600;
  line-height: 1.3;
  letter-spacing: 0.03em;
  display: flex;
  flex-direction: column;
}

.brand-line1 {
  font-size: 14px;
}

.brand-line2 {
  font-size: 12px;
  opacity: 0.85;
}

.header {
  z-index: 98;
  background: var(--brand-surface, #fff);
  padding: 0 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid var(--brand-line, #e6e2da);
  height: 64px;
  line-height: 1.2;
  box-shadow: 0 1px 0 0 var(--brand-line, #d9c9a3);
  transition: background 0.3s, border-color 0.3s;
}

.trigger {
  color: var(--brand-ink, #0d0d0d);
  font-size: 18px;
}

.header-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.header-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--brand-ink, #0d0d0d);
  letter-spacing: 0.04em;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.lang-icon {
  color: var(--brand-muted, #6b6b6b);
  font-size: 16px;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 6px;
  cursor: pointer;
  color: var(--brand-ink, #0d0d0d);
  transition: background 0.18s ease;

  &:hover {
    background: var(--brand-line, #f2efe9);
  }
}

.user-icon {
  color: var(--brand-primary, #c4a574);
}

.user-name {
  font-weight: 500;
}

/* ═══ 標籤頁欄 ═══ */
.tabs-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 16px;
  background: var(--brand-surface, #fff);
  border-bottom: 1px solid var(--brand-line, #e6e2da);
  overflow-x: auto;
  white-space: nowrap;
  transition: background 0.3s, border-color 0.3s;

  &::-webkit-scrollbar {
    height: 3px;
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(196, 165, 116, 0.35);
    border-radius: 2px;
  }
}

.tabs-button .tab-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  color: var(--brand-muted, #6b6b6b);
  background: transparent;
  transition: all 0.18s ease;

  &:hover {
    color: var(--brand-ink, #0d0d0d);
    background: var(--brand-line, #f2efe9);
  }

  &.active {
    color: var(--brand-primary, #c4a574);
    background: var(--brand-line, #f2efe9);
    font-weight: 600;
  }

  .tab-icon {
    font-size: 12px;
  }

  .tab-title {
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .tab-close {
    font-size: 10px;
    padding: 2px;
    border-radius: 50%;
    opacity: 0;
    transition: opacity 0.15s, background 0.15s;
    color: var(--brand-muted, #999);

    &:hover {
      background: rgba(0, 0, 0, 0.08);
      color: #333;
    }
  }

  &:hover .tab-close {
    opacity: 1;
  }
}

.tabs-card .tab-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border: 1px solid var(--brand-line, #e6e2da);
  border-radius: 4px 4px 0 0;
  font-size: 12px;
  cursor: pointer;
  color: var(--brand-muted, #6b6b6b);
  background: var(--brand-surface, #fafafa);
  margin-bottom: -1px;
  transition: all 0.18s ease;

  &:hover {
    color: var(--brand-ink, #0d0d0d);
    background: var(--brand-canvas, #f7f7f5);
  }

  &.active {
    color: var(--brand-primary, #c4a574);
    background: var(--brand-surface, #fff);
    border-bottom-color: var(--brand-surface, #fff);
    font-weight: 600;
  }

  .tab-icon {
    font-size: 12px;
  }

  .tab-title {
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .tab-close {
    font-size: 10px;
    padding: 2px;
    border-radius: 50%;
    opacity: 0;
    transition: opacity 0.15s, background 0.15s;
    color: var(--brand-muted, #999);

    &:hover {
      background: rgba(0, 0, 0, 0.08);
      color: #333;
    }
  }

  &:hover .tab-close {
    opacity: 1;
  }
}

/* ═══ 標籤右鍵菜單 ═══ */
.tab-context-menu {
  position: fixed;
  z-index: 3000;
  min-width: 140px;
  background: var(--brand-surface, #fff);
  border: 1px solid var(--brand-line, #e6e2da);
  border-radius: 6px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.12);
  padding: 4px;
  transition: background 0.3s, border-color 0.3s;

  :deep(.ant-menu) {
    background: transparent;
    border: none;
  }

  :deep(.ant-menu-item) {
    height: 32px;
    line-height: 32px;
    font-size: 13px;
    border-radius: 4px;
    margin: 2px 0;
    color: var(--brand-ink, #0d0d0d);
  }

  :deep(.ant-menu-item:hover) {
    background: var(--brand-line, #f2efe9);
    color: var(--brand-primary, #c4a574);
  }

  :deep(.ant-menu-item-divider) {
    margin: 4px 8px;
    background: var(--brand-line, #e6e2da);
  }
}

.content {
  margin: 16px;
  min-height: calc((100vh / var(--ls-scale, 1)) - var(--ls-content-offset, 96px));
  background: var(--brand-canvas, #f7f7f5);
  transition: background 0.3s;
}

.content.ls-content {
  margin: 0;
}

.header-fixed {
  position: sticky;
  top: 0;
}

.header-static {
  position: relative;
}

.footer {
  text-align: center;
  padding: 16px;
  color: var(--brand-muted, #6b6b6b);
  font-size: 12px;
  background: var(--brand-surface, #f7f7f5);
  border-top: 1px solid var(--brand-line, #e6e2da);
  transition: background 0.3s, border-color 0.3s;
}
</style>
