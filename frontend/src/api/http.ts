import axios from 'axios'
import { message } from 'ant-design-vue'
import router from '@/router'
import i18n from '@/i18n'

/** 登录凭证在 localStorage 的存储键（与 stores/user.ts 共用） */
export const TOKEN_STORAGE_KEY = '333-iot-console-token'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/',
  timeout: 15000,
})

// 请求拦截：自动附加 JWT Token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截：统一错误提示 + 401 跳转登录
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status: number | undefined = error.response?.status
    const detail: string | undefined = error.response?.data?.detail
    if (status === 401) {
      localStorage.removeItem(TOKEN_STORAGE_KEY)
      const current = router.currentRoute.value
      if (current.path !== '/login') {
        message.error(detail || i18n.global.t('common.sessionExpired'))
        router.push({ path: '/login', query: { redirect: current.fullPath } })
      }
    } else {
      message.error(detail || error.message || i18n.global.t('common.requestFailed'))
    }
    return Promise.reject(error)
  },
)

export default api
