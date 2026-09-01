<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { RightOutlined, LogoutOutlined } from '@ant-design/icons-vue'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'
import { usePermissionStore } from '@/stores/permission'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'

const { t } = useI18n()
const appStore = useAppStore()
const userStore = useUserStore()
const permissionStore = usePermissionStore()
const router = useRouter()

const password = ref('')
const currentTime = ref('')
const currentDate = ref('')
let timer: ReturnType<typeof setInterval> | null = null

const displayName = computed(
  () => userStore.userInfo?.nickname || userStore.userInfo?.username || '',
)

function updateTime() {
  currentTime.value = dayjs().format('HH:mm:ss')
  const locale = appStore.locale
  if (locale === 'zh-TW') {
    currentDate.value = dayjs().format('YYYY年M月D日 dddd')
  } else {
    currentDate.value = dayjs().format('MMMM D, YYYY dddd')
  }
}

onMounted(() => {
  updateTime()
  timer = setInterval(updateTime, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

async function handleUnlock() {
  if (!password.value) {
    message.warning(t('login.required'))
    return
  }
  try {
    await userStore.login(
      userStore.userInfo?.username || '',
      password.value,
    )
    appStore.unlockScreen()
    password.value = ''
    message.success(t('lockScreen.unlockSuccess'))
  } catch {
    message.error(t('lockScreen.unlockFailed'))
    password.value = ''
  }
}

async function handleExit() {
  await userStore.logout()
  permissionStore.reset()
  appStore.unlockScreen()
  router.push('/login')
  message.success(t('lockScreen.exitSuccess'))
}
</script>

<template>
  <div class="lock-screen-overlay">
    <div class="lock-screen-bg"></div>

    <div class="lock-screen-content">
      <div class="time-section">
        <div class="time-display">{{ currentTime }}</div>
        <div class="date-display">{{ currentDate }}</div>
      </div>

      <div class="lock-card">
        <a-avatar :size="72" class="lock-avatar">
          <template #icon>
            <span style="font-size: 36px">👤</span>
          </template>
        </a-avatar>
        <div class="lock-username">{{ displayName }}</div>
        <div class="lock-hint">{{ t('lockScreen.title') }}</div>

        <div class="password-input-wrapper">
          <input
            v-model="password"
            type="password"
            :placeholder="t('lockScreen.passwordPlaceholder')"
            class="lock-password-input"
            @keydown.enter="handleUnlock"
          />
          <a-button type="primary" shape="circle" class="unlock-btn" @click="handleUnlock">
            <template #icon>
              <RightOutlined />
            </template>
          </a-button>
        </div>

        <a-button type="link" class="exit-btn" @click="handleExit">
          <LogoutOutlined />
          {{ t('lockScreen.exitReLogin') }}
        </a-button>
      </div>
    </div>
  </div>
</template>

<style scoped lang="less">
.lock-screen-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.lock-screen-bg {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 30%, #0f3460 60%, #1a1a2e 100%);
  z-index: 0;

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background-image:
      radial-gradient(1px 1px at 20% 30%, rgba(255,255,255,0.5) 0%, transparent 100%),
      radial-gradient(1px 1px at 40% 70%, rgba(255,255,255,0.4) 0%, transparent 100%),
      radial-gradient(1px 1px at 60% 20%, rgba(255,255,255,0.3) 0%, transparent 100%),
      radial-gradient(1px 1px at 80% 50%, rgba(255,255,255,0.5) 0%, transparent 100%),
      radial-gradient(1px 1px at 10% 80%, rgba(255,255,255,0.3) 0%, transparent 100%),
      radial-gradient(1px 1px at 70% 90%, rgba(255,255,255,0.4) 0%, transparent 100%),
      radial-gradient(1px 1px at 90% 10%, rgba(255,255,255,0.3) 0%, transparent 100%),
      radial-gradient(1px 1px at 30% 50%, rgba(255,255,255,0.2) 0%, transparent 100%),
      radial-gradient(1px 1px at 50% 40%, rgba(255,255,255,0.4) 0%, transparent 100%);
  }
}

.lock-screen-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 40px;
}

.time-section {
  text-align: center;
}

.time-display {
  font-size: 72px;
  font-weight: 200;
  color: rgba(255, 255, 255, 0.9);
  letter-spacing: 8px;
  font-variant-numeric: tabular-nums;
}

.date-display {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.6);
  margin-top: 8px;
  letter-spacing: 2px;
}

.lock-card {
  background: rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 16px;
  padding: 32px;
  width: 340px;
  display: flex;
  flex-direction: column;
  align-items: center;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.lock-avatar {
  background: linear-gradient(135deg, #c4a574, #d4b88a);
  color: #fff;
  margin-bottom: 12px;
}

.lock-username {
  font-size: 20px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 8px;
}

.lock-hint {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.55);
  margin-bottom: 24px;
  text-align: center;
}

.password-input-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  margin-bottom: 16px;

  .lock-password-input {
    flex: 1;
    height: 36px;
    padding: 4px 16px;
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: #fff;
    font-size: 14px;
    outline: none;
    transition: border-color 0.2s, background 0.2s;

    &::placeholder {
      color: rgba(255, 255, 255, 0.4);
    }

    &:focus {
      border-color: rgba(196, 165, 116, 0.6);
      background: rgba(255, 255, 255, 0.15);
    }

    &:-webkit-autofill {
      -webkit-box-shadow: 0 0 0 1000px rgba(255, 255, 255, 0.1) inset !important;
      -webkit-text-fill-color: #fff !important;
    }
  }

  .unlock-btn {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: rgba(196, 165, 116, 0.7);
    border-color: rgba(196, 165, 116, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;

    &:hover {
      background: #c4a574;
      border-color: #c4a574;
    }
  }
}

.exit-btn {
  color: rgba(255, 255, 255, 0.5) !important;
  font-size: 13px;
  padding: 0;

  &:hover {
    color: rgba(255, 255, 255, 0.8) !important;
  }
}
</style>
