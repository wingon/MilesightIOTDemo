<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { UserOutlined, MobileOutlined, MailOutlined, TeamOutlined, SafetyOutlined, CalendarOutlined } from '@ant-design/icons-vue'
import { useUserStore } from '@/stores/user'
import { getUserProfile, updateUserProfile, updateUserPwd } from '@/api/profile'

const { t } = useI18n()
const userStore = useUserStore()

const activeTab = ref('basic')
const loading = ref(false)
const passwordLoading = ref(false)

const userInfo = computed(() => userStore.userInfo)

const profileForm = reactive({
  nickname: '',
  phonenumber: '',
  email: '',
  sex: '0' as string,
})

const passwordForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

onMounted(async () => {
  await loadProfile()
})

async function loadProfile() {
  try {
    const res = await getUserProfile()
    const data = res.data
    profileForm.nickname = data.nickName || userInfo.value?.nickname || ''
    profileForm.phonenumber = data.phonenumber || ''
    profileForm.email = data.email || ''
    profileForm.sex = data.sex || '0'
  } catch {
    // 如果 API 失敗，使用 store 中的數據
    if (userInfo.value) {
      profileForm.nickname = userInfo.value.nickname || ''
    }
  }
}

watch(() => userInfo.value, (val) => {
  if (val) {
    profileForm.nickname = val.nickname || ''
  }
}, { immediate: true })

async function handleSaveProfile() {
  loading.value = true
  try {
    await updateUserProfile({
      nickName: profileForm.nickname,
      phonenumber: profileForm.phonenumber,
      email: profileForm.email,
      sex: profileForm.sex,
    })
    // 重新載入用戶信息以同步更新
    await userStore.fetchUserInfo()
    message.success(t('profile.saveSuccess'))
  } catch {
    message.error(t('profile.saveFailed'))
  } finally {
    loading.value = false
  }
}

async function handleChangePassword() {
  if (!passwordForm.oldPassword) {
    message.warning(t('profile.oldPassword') + ' ' + t('system.required'))
    return
  }
  if (!passwordForm.newPassword) {
    message.warning(t('profile.newPassword') + ' ' + t('system.required'))
    return
  }
  if (passwordForm.newPassword.length < 6) {
    message.error(t('profile.passwordMin'))
    return
  }
  if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    message.error(t('profile.passwordMismatch'))
    return
  }
  passwordLoading.value = true
  try {
    await updateUserPwd(passwordForm.oldPassword, passwordForm.newPassword)
    message.success(t('profile.passwordSaveSuccess'))
    passwordForm.oldPassword = ''
    passwordForm.newPassword = ''
    passwordForm.confirmPassword = ''
  } catch {
    message.error(t('profile.passwordSaveFailed'))
  } finally {
    passwordLoading.value = false
  }
}
</script>

<template>
  <div class="profile-page">
    <div class="profile-left">
      <div class="info-card">
        <h3 class="card-title">{{ t('profile.personalInfo') }}</h3>
        <div class="avatar-section">
          <a-avatar :size="100" class="user-avatar">
            <template #icon>
              <UserOutlined />
            </template>
          </a-avatar>
        </div>
        <div class="info-list">
          <div class="info-item">
            <UserOutlined class="info-icon" />
            <span class="info-label">{{ t('profile.username') }}</span>
            <span class="info-value">{{ userInfo?.username }}</span>
          </div>
          <div class="info-item">
            <MobileOutlined class="info-icon" />
            <span class="info-label">{{ t('profile.phone') }}</span>
            <span class="info-value">{{ profileForm.phonenumber || '-' }}</span>
          </div>
          <div class="info-item">
            <MailOutlined class="info-icon" />
            <span class="info-label">{{ t('profile.email') }}</span>
            <span class="info-value">{{ profileForm.email || '-' }}</span>
          </div>
          <div class="info-item">
            <TeamOutlined class="info-icon" />
            <span class="info-label">{{ t('profile.department') }}</span>
            <span class="info-value">-</span>
          </div>
          <div class="info-item">
            <SafetyOutlined class="info-icon" />
            <span class="info-label">{{ t('profile.role') }}</span>
            <span class="info-value">{{ userStore.roles.join(', ') || '-' }}</span>
          </div>
          <div class="info-item">
            <CalendarOutlined class="info-icon" />
            <span class="info-label">{{ t('profile.createdAt') }}</span>
            <span class="info-value">-</span>
          </div>
        </div>
      </div>
    </div>

    <div class="profile-right">
      <div class="form-card">
        <h3 class="card-title">{{ t('profile.basicInfo') }}</h3>
        <a-tabs v-model:activeKey="activeTab">
          <a-tab-pane key="basic" :tab="t('profile.basicInfo')">
            <a-form :model="profileForm" layout="vertical" class="profile-form">
              <a-form-item :label="t('profile.nickname')" required>
                <a-input v-model:value="profileForm.nickname" :placeholder="t('profile.nickname')" />
              </a-form-item>
              <a-form-item :label="t('profile.phone')">
                <a-input v-model:value="profileForm.phonenumber" :placeholder="t('profile.phone')" />
              </a-form-item>
              <a-form-item :label="t('profile.email')">
                <a-input v-model:value="profileForm.email" :placeholder="t('profile.email')" />
              </a-form-item>
              <a-form-item :label="t('profile.gender')">
                <a-radio-group v-model:value="profileForm.sex">
                  <a-radio value="0">{{ t('profile.genderMale') }}</a-radio>
                  <a-radio value="1">{{ t('profile.genderFemale') }}</a-radio>
                </a-radio-group>
              </a-form-item>
              <a-form-item>
                <a-space>
                  <a-button type="primary" :loading="loading" @click="handleSaveProfile">
                    {{ t('profile.save') }}
                  </a-button>
                  <a-button danger>
                    {{ t('profile.close') }}
                  </a-button>
                </a-space>
              </a-form-item>
            </a-form>
          </a-tab-pane>

          <a-tab-pane key="password" :tab="t('profile.changePassword')">
            <a-form :model="passwordForm" layout="vertical" class="profile-form">
              <a-form-item :label="t('profile.oldPassword')" required>
                <a-input-password v-model:value="passwordForm.oldPassword" :placeholder="t('profile.oldPassword')" />
              </a-form-item>
              <a-form-item :label="t('profile.newPassword')" required>
                <a-input-password v-model:value="passwordForm.newPassword" :placeholder="t('profile.newPassword')" />
              </a-form-item>
              <a-form-item :label="t('profile.confirmPassword')" required>
                <a-input-password v-model:value="passwordForm.confirmPassword" :placeholder="t('profile.confirmPassword')" />
              </a-form-item>
              <a-form-item>
                <a-space>
                  <a-button type="primary" :loading="passwordLoading" @click="handleChangePassword">
                    {{ t('profile.save') }}
                  </a-button>
                  <a-button danger>
                    {{ t('profile.close') }}
                  </a-button>
                </a-space>
              </a-form-item>
            </a-form>
          </a-tab-pane>
        </a-tabs>
      </div>
    </div>
  </div>
</template>

<style scoped lang="less">
.profile-page {
  display: flex;
  gap: 20px;
  padding: 20px;
}

.profile-left {
  flex: 0 0 380px;
}

.profile-right {
  flex: 1;
}

.info-card,
.form-card {
  background: var(--brand-surface, #fff);
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #0d0d0d;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e6e2da;
}

.avatar-section {
  display: flex;
  justify-content: center;
  margin-bottom: 24px;
}

.user-avatar {
  background: #c4a574;
  color: #fff;
  font-size: 42px;
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px dashed #f0ece5;
}

.info-icon {
  color: #c4a574;
  font-size: 15px;
  width: 20px;
  text-align: center;
}

.info-label {
  color: #6b6b6b;
  min-width: 80px;
  font-size: 13px;
}

.info-value {
  color: #0d0d0d;
  font-weight: 500;
  flex: 1;
  text-align: right;
}

.profile-form {
  max-width: 500px;
}
</style>
