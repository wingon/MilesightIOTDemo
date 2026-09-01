<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

const router = useRouter()
const { t } = useI18n()
</script>

<template>
  <div class="not-found">
    <div class="code">404</div>
    <div class="desc">{{ t('common.notFound') }}</div>
    <a-button type="primary" @click="router.push('/')">{{ t('common.backHome') }}</a-button>
  </div>
</template>

<style scoped lang="less">
.not-found {
  min-height: 60vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.code {
  font-size: 72px;
  font-weight: 700;
  color: #c4a574;
  line-height: 1;
}

.desc {
  color: #6b6b6b;
  font-size: 16px;
}
</style>
