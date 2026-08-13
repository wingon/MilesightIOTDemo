<script setup lang="ts">
import { computed, h } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import {
  DashboardOutlined,
  ThunderboltOutlined,
  CloudOutlined,
  TeamOutlined,
  BankOutlined,
  ApiOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  GlobalOutlined,
} from '@ant-design/icons-vue'
import { useAppStore } from '@/stores/app'
import type { AppLocale } from '@/i18n'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const appStore = useAppStore()

const selectedKeys = computed(() => {
  const name = String(route.name || 'dashboard')
  if (name === 'floor-viewer') return ['building-viewer']
  return [name]
})

const brandLine1 = computed(() => String(t('common.brandLine1')))
const brandLine2 = computed(() => String(t('common.brandLine2')))

const menuItems = computed(() =>
  [
    {
      key: 'dashboard',
      icon: () => h(DashboardOutlined),
      label: t('menu.dashboard'),
      path: '/',
    },
    {
      key: 'ct103',
      icon: () => h(ThunderboltOutlined),
      label: t('menu.tof'),
      path: '/ct103',
      hidden: true,
    },
    {
      key: 'ug65',
      icon: () => h(CloudOutlined),
      label: t('menu.ug65'),
      path: '/ug65',
      hidden: true,
    },
    {
      key: 'vs135',
      icon: () => h(TeamOutlined),
      label: t('menu.vs135'),
      path: '/vs135',
      hidden: true,
    },
    {
      key: 'building-viewer',
      icon: () => h(BankOutlined),
      label: t('menu.buildingViewer'),
      path: '/building-viewer',
    },
    {
      key: 'devices',
      icon: () => h(ApiOutlined),
      label: t('menu.devices'),
      path: '/devices',
    },
  ].filter((item) => !item.hidden)
)

const pageTitle = computed(() => {
  const key = route.meta.titleKey as string | undefined
  return key ? t(key) : t('common.brand')
})

const localeOptions = computed(() => [
  { value: 'en', label: t('common.english') },
  { value: 'zh-TW', label: t('common.zhTw') },
])

const mainOffset = computed(() => (appStore.sidebarCollapsed ? '80px' : '240px'))

function onMenuClick(info: { key: string | number }) {
  const item = menuItems.value.find((m) => m.key === info.key)
  if (item) router.push(item.path)
}

function onLocaleChange(value: unknown) {
  appStore.setLocale(value as AppLocale)
  const key = route.meta.titleKey as string | undefined
  const title = key ? t(key) : t('common.brand')
  document.title = `${title} · ${t('common.brand')}`
}
</script>

<template>
  <a-layout class="shell">
    <a-layout-sider
      collapsible
      :collapsed="appStore.sidebarCollapsed"
      :trigger="null"
      width="240"
      :collapsed-width="80"
      theme="dark"
      class="sider"
    >
      <div class="brand" :class="{ collapsed: appStore.sidebarCollapsed }">
        <img class="brand-logo" src="/wingon-logo.png" alt="Wing On" />
        <div v-if="!appStore.sidebarCollapsed" class="brand-text">
          <div class="brand-name">
            <span class="brand-line1">{{ brandLine1 }}</span>
            <span class="brand-line2">{{ brandLine2 }}</span>
          </div>
        </div>
      </div>
      <a-menu
        theme="dark"
        mode="inline"
        :selected-keys="selectedKeys"
        :items="menuItems"
        @click="onMenuClick"
      />
    </a-layout-sider>

    <a-layout class="main" :style="{ marginLeft: mainOffset }">
      <a-layout-header class="header">
        <a-button type="text" class="trigger" @click="appStore.toggleSidebar">
          <MenuUnfoldOutlined v-if="appStore.sidebarCollapsed" />
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
        </div>
      </a-layout-header>

      <a-layout-content class="content">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<style scoped lang="less">
.shell {
  min-height: 100vh;
  background: #f7f7f5;
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

  :deep(.ant-menu-dark .ant-menu-item-selected) {
    background: #c4a574 !important;
    color: #0d0d0d !important;
    font-weight: 600;
  }

  :deep(.ant-menu-dark .ant-menu-item-selected .anticon) {
    color: #0d0d0d !important;
  }
}

.main {
  min-height: 100vh;
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
  position: sticky;
  top: 0;
  z-index: 98;
  background: #fff;
  padding: 0 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid #e6e2da;
  height: 64px;
  line-height: 1.2;
}

.trigger {
  color: #0d0d0d;
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
  font-weight: 650;
  color: #0d0d0d;
  letter-spacing: 0.02em;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.lang-icon {
  color: #6b6b6b;
  font-size: 16px;
}

.content {
  margin: 16px;
  min-height: calc(100vh - 96px);
}
</style>
