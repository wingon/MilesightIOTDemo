<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { LockOutlined, UserOutlined, GlobalOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/stores/user'
import { usePermissionStore } from '@/stores/permission'
import { LOCALE_STORAGE_KEY, type AppLocale } from '@/i18n'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const permissionStore = usePermissionStore()

const REMEMBER_KEY = '333-iot-remember-me'
const remember = ref(false)
const loading = ref(false)
const form = reactive({ username: '', password: '' })

onMounted(() => {
  try {
    const saved = localStorage.getItem(REMEMBER_KEY)
    if (saved) {
      const { username, password } = JSON.parse(saved)
      form.username = username || ''
      form.password = password || ''
      remember.value = true
    }
  } catch { /* ignore */ }
})

function switchLocale(lang: AppLocale) {
  locale.value = lang
  localStorage.setItem(LOCALE_STORAGE_KEY, lang)
}

async function onSubmit() {
  if (!form.username || !form.password) {
    message.warning(t('login.required'))
    return
  }
  loading.value = true
  try {
    if (remember.value) {
      localStorage.setItem(REMEMBER_KEY, JSON.stringify({ username: form.username, password: form.password }))
    } else {
      localStorage.removeItem(REMEMBER_KEY)
    }
    await userStore.login(form.username, form.password)
    await userStore.fetchUserInfo()
    await permissionStore.generateRoutes()
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch {
    // 错误提示已由 http 拦截器统一处理
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <img class="login-logo" src="/wingon-logo.png" alt="Wing On" />
      <div class="login-title">{{ t('login.title') }}</div>
      <div class="login-subtitle">{{ t('login.subtitle') }}</div>
      <a-form layout="vertical" @finish="onSubmit" @submit.prevent>
        <a-form-item>
          <a-input
            v-model:value="form.username"
            size="large"
            :placeholder="t('login.username')"
            autocomplete="username"
          >
            <template #prefix><UserOutlined /></template>
          </a-input>
        </a-form-item>
        <a-form-item>
          <a-input-password
            v-model:value="form.password"
            size="large"
            :placeholder="t('login.password')"
            autocomplete="current-password"
            @press-enter="onSubmit"
          >
            <template #prefix><LockOutlined /></template>
          </a-input-password>
        </a-form-item>
        <div class="login-options">
          <a-checkbox v-model:checked="remember">{{ t('login.remember') }}</a-checkbox>
        </div>
        <a-button
          type="primary"
          html-type="submit"
          block
          size="large"
          :loading="loading"
          class="login-btn"
          @click="onSubmit"
        >
          {{ t('login.submit') }}
        </a-button>
      </a-form>
      <div class="login-lang">
        <GlobalOutlined class="login-lang-icon" />
        <a
          :class="{ active: locale === 'en' }"
          @click.prevent="switchLocale('en')"
        >English</a>
        <span class="login-lang-sep">|</span>
        <a
          :class="{ active: locale === 'zh-TW' }"
          @click.prevent="switchLocale('zh-TW')"
        >繁體中文</a>
      </div>
    </div>
  </div>
</template>

<style scoped lang="less">
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(1200px 600px at 20% 10%, rgba(196, 165, 116, 0.18), transparent 60%),
    radial-gradient(1000px 500px at 90% 90%, rgba(196, 165, 116, 0.12), transparent 55%),
    #1a1a1a;
  padding: 24px;
}

.login-card {
  width: 380px;
  max-width: 100%;
  background: #232323;
  border: 1px solid rgba(196, 165, 116, 0.25);
  border-radius: 12px;
  padding: 40px 36px 28px;
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.45);
}

.login-logo {
  display: block;
  width: 72px;
  height: auto;
  margin: 0 auto 16px;
  object-fit: contain;
}

.login-title {
  text-align: center;
  color: #f5ead7;
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 0.05em;
}

.login-subtitle {
  text-align: center;
  color: #9b9b93;
  font-size: 13px;
  margin: 6px 0 24px;
}

.login-btn {
  background: #c4a574;
  border-color: #c4a574;
  color: #0d0d0d;
  font-weight: 600;
  letter-spacing: 0.06em;

  &:hover,
  &:focus {
    background: #d4b889 !important;
    border-color: #d4b889 !important;
    color: #0d0d0d !important;
  }
}

.login-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
}

.login-lang {
  margin-top: 20px;
  text-align: center;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;

  a {
    color: #6b6b6b;
    cursor: pointer;
    transition: color 0.2s;
    text-decoration: none;

    &:hover,
    &.active {
      color: #c4a574;
    }
  }
}

.login-lang-icon {
  color: #6b6b6b;
  margin-right: 2px;
}

.login-lang-sep {
  color: #3a3a3a;
  margin: 0 6px;
}

:deep(.ant-form-item) {
  margin-bottom: 18px;
}

:deep(.ant-input-affix-wrapper) {
  background: #2b2b2b;
  border-color: #3a3a3a;
  color: #f5ead7;
}

:deep(.ant-input) {
  background: transparent;
  color: #f5ead7;
}

:deep(.ant-input-prefix) {
  color: #8a8a82;
}

:deep(.ant-input::placeholder) {
  color: #6b6b6b;
}
</style>
