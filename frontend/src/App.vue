<script setup lang="ts">
import { computed, watch, onMounted } from 'vue'
import type { ThemeConfig } from 'ant-design-vue/es/config-provider/context'
import { ConfigProvider, theme } from 'ant-design-vue'
import enUS from 'ant-design-vue/es/locale/en_US'
import zhTW from 'ant-design-vue/es/locale/zh_TW'
import { brand } from '@/theme/colorConfig'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

const themeConfig = computed<ThemeConfig>(() => ({
  token: {
    colorPrimary: appStore.layoutConfig.themeColor || brand.primary,
    colorInfo: appStore.layoutConfig.themeColor || brand.primary,
    colorSuccess: brand.success,
    colorError: brand.danger,
    colorTextBase: appStore.layoutConfig.themeMode === 'dark' ? '#e0e0e0' : brand.ink,
    colorBgBase: appStore.layoutConfig.themeMode === 'dark' ? '#1f1f1f' : brand.surface,
    colorBgLayout: appStore.layoutConfig.themeMode === 'dark' ? '#141414' : brand.canvas,
    borderRadius: 2,
    fontFamily:
      '"Segoe UI", "PingFang TC", "Microsoft JhengHei", "Helvetica Neue", Arial, sans-serif',
    controlHeight: 36,
  },
  algorithm: appStore.layoutConfig.themeMode === 'dark'
    ? theme.darkAlgorithm
    : theme.defaultAlgorithm,
}))

const antdLocale = computed(() =>
  appStore.locale === 'zh-TW' ? zhTW : enUS,
)

function applyThemeClass() {
  const isDark = appStore.layoutConfig.themeMode === 'dark'
  document.documentElement.classList.toggle('theme-dark', isDark)
  document.documentElement.classList.toggle('theme-light', !isDark)
}

function applyBrandColor() {
  const color = appStore.layoutConfig.themeColor || '#C4A574'
  document.documentElement.style.setProperty('--brand-primary', color)
  document.documentElement.style.setProperty('--brand-color', color)
}

watch(
  () => appStore.layoutConfig.themeMode,
  () => applyThemeClass(),
  { immediate: true },
)

watch(
  () => appStore.layoutConfig.themeColor,
  () => applyBrandColor(),
  { immediate: true },
)

onMounted(() => {
  appStore.initLocale()
  applyThemeClass()
  applyBrandColor()
})
</script>

<template>
  <ConfigProvider :locale="antdLocale" :theme="themeConfig">
    <router-view />
  </ConfigProvider>
</template>
