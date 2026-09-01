import api from './http'

/** 当前用户信息（/api/v1/auth/userinfo 返回结构） */
export interface UserInfoPayload {
  user: {
    id: number
    username: string
    nickname?: string | null
    avatar?: string | null
  }
  roles: string[]
  permissions: string[]
}

/** 后端菜单树节点（/api/v1/auth/routes 返回结构） */
export interface MenuNode {
  id: number
  parent_id: number
  menu_name: string
  i18n_key?: string | null
  path?: string | null
  component?: string | null
  menu_type: 'M' | 'C' | 'F'
  permission?: string | null
  icon?: string | null
  sort: number
  visible: number
  status: number
  remark?: string | null
  children?: MenuNode[]
}

/** 登录，返回 JWT Token */
export function login(username: string, password: string) {
  return api.post<{ token: string }>('/api/v1/auth/login', { username, password })
}

/** 登出（无状态，后端仅作记录） */
export function logout() {
  return api.post('/api/v1/auth/logout')
}

/** 获取当前用户信息：基本信息 + 角色 + 权限集合 */
export function getUserInfo() {
  return api.get<UserInfoPayload>('/api/v1/auth/userinfo')
}

/** 获取当前用户可见菜单树（动态路由与侧边栏用） */
export function getUserRoutes() {
  return api.get<MenuNode[]>('/api/v1/auth/routes')
}

/** 获取启用中的前端路由白名单（免登录路径前缀，公开接口） */
export function getFrontWhitelist() {
  return api.get<string[]>('/api/v1/auth/whitelist')
}
