import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  getUserInfo,
  login as loginApi,
  logout as logoutApi,
} from '@/api/auth'
import { TOKEN_STORAGE_KEY } from '@/api/http'

export const useUserStore = defineStore('user', () => {
  const token = ref<string>(localStorage.getItem(TOKEN_STORAGE_KEY) || '')
  const userInfo = ref<{ id: number; username: string; nickname?: string | null; avatar?: string | null } | null>(null)
  const roles = ref<string[]>([])
  const permissions = ref<string[]>([])

  function setToken(value: string) {
    token.value = value
    if (value) localStorage.setItem(TOKEN_STORAGE_KEY, value)
    else localStorage.removeItem(TOKEN_STORAGE_KEY)
  }

  async function login(username: string, password: string) {
    const res = await loginApi(username, password)
    setToken(res.data.token)
  }

  async function fetchUserInfo() {
    const res = await getUserInfo()
    userInfo.value = res.data.user
    roles.value = res.data.roles
    permissions.value = res.data.permissions
    return res.data
  }

  /** 判断是否拥有某个权限标识（空值放行；admin 或 *:*:* 全放行） */
  function hasPermission(perm?: string): boolean {
    if (!perm) return true
    if (roles.value.includes('admin')) return true
    if (permissions.value.includes('*:*:*')) return true
    return permissions.value.includes(perm)
  }

  function reset() {
    setToken('')
    userInfo.value = null
    roles.value = []
    permissions.value = []
  }

  async function logout() {
    try {
      await logoutApi()
    } catch {
      // 忽略登出接口失败，本地凭证必须清除
    }
    reset()
  }

  return {
    token,
    userInfo,
    roles,
    permissions,
    login,
    fetchUserInfo,
    hasPermission,
    logout,
    reset,
  }
})
