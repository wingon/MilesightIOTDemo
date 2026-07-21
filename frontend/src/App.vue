<script setup lang="ts">
import { computed, onMounted } from 'vue'
import type { ThemeConfig } from 'ant-design-vue/es/config-provider/context'
import { ConfigProvider, theme } from 'ant-design-vue'
import enUS from 'ant-design-vue/es/locale/en_US'
import zhTW from 'ant-design-vue/es/locale/zh_TW'
import { antThemeToken } from '@/theme/colorConfig'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

const themeConfig: ThemeConfig = {
  token: antThemeToken,
  algorithm: theme.defaultAlgorithm,
}

const antdLocale = computed(() =>
  appStore.locale === 'zh-TW' ? zhTW : enUS,
)

onMounted(() => {
  appStore.initLocale()
})
</script>

<template>
  <ConfigProvider :locale="antdLocale" :theme="themeConfig">
    <router-view />
  </ConfigProvider>
</template>
