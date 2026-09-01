import api from './http'
import type { MenuNode } from './auth'

// ---------- 通用分页结构 ----------
export interface PageResult<T> {
  total: number
  limit: number
  offset: number
  items: T[]
}

// ---------- 用户管理 ----------
export interface SysUserRow {
  id: number
  dept_id?: number | null
  dept_name?: string | null
  username: string
  nickname?: string | null
  email?: string | null
  phone?: string | null
  status: number
  remark?: string | null
  roles?: string | null
  role_keys?: string | null
  created_at?: string
  updated_at?: string
}

export interface SysUserBody {
  username?: string
  password?: string
  dept_id?: number | null
  nickname?: string | null
  email?: string | null
  phone?: string | null
  status?: number
  remark?: string | null
}

export function listUsers(params: {
  keyword?: string
  status?: number
  dept_id?: number
  offset?: number
  limit?: number
}) {
  return api.get<PageResult<SysUserRow>>('/api/v1/system/user/list', { params })
}

export function getUserRoleIds(userId: number) {
  return api.get<number[]>(`/api/v1/system/user/${userId}/roles`)
}

export function getUserPostIds(userId: number) {
  return api.get<number[]>(`/api/v1/system/user/${userId}/posts`)
}

export function createUser(body: SysUserBody) {
  return api.post<{ id: number }>('/api/v1/system/user', body)
}

export function updateUser(userId: number, body: SysUserBody) {
  return api.put<{ ok: boolean }>(`/api/v1/system/user/${userId}`, body)
}

export function resetUserPassword(userId: number, password: string) {
  return api.put<{ ok: boolean }>(`/api/v1/system/user/${userId}/password`, { password })
}

export function assignUserRoles(userId: number, roleIds: number[]) {
  return api.put<{ ok: boolean }>(`/api/v1/system/user/${userId}/roles`, { role_ids: roleIds })
}

export function assignUserPosts(userId: number, postIds: number[]) {
  return api.put<{ ok: boolean }>(`/api/v1/system/user/${userId}/posts`, { post_ids: postIds })
}

export function deleteUser(userId: number) {
  return api.delete<{ ok: boolean }>(`/api/v1/system/user/${userId}`)
}

// ---------- 角色管理 ----------
export interface SysRoleRow {
  id: number
  role_name: string
  role_key: string
  sort: number
  status: number
  data_scope?: string
  remark?: string | null
  created_at?: string
  updated_at?: string
}

export interface SysRoleBody {
  role_name: string
  role_key: string
  sort?: number
  status?: number
  data_scope?: string
  remark?: string | null
}

export interface DataScopeBody {
  data_scope?: string
  dept_ids?: number[]
}

export function listRoles(params: {
  role_name?: string
  role_key?: string
  status?: number
  begin?: string
  end?: string
  offset?: number
  limit?: number
}) {
  return api.get<PageResult<SysRoleRow>>('/api/v1/system/role/list', { params })
}

export function listRoleOptions() {
  return api.get<SysRoleRow[]>('/api/v1/system/role/options')
}

export function getRole(roleId: number) {
  return api.get<SysRoleRow>(`/api/v1/system/role/${roleId}`)
}

export function getRoleMenuIds(roleId: number) {
  return api.get<number[]>(`/api/v1/system/role/${roleId}/menus`)
}

export function getRoleDeptIds(roleId: number) {
  return api.get<number[]>(`/api/v1/system/role/${roleId}/depts`)
}

export function getRoleMenuTree() {
  return api.get<{ menus: MenuNode[] }>('/api/v1/system/role/menu-tree')
}

export function getRoleDeptTree() {
  return api.get<{ depts: SysDeptRow[] }>('/api/v1/system/role/dept-tree')
}

export function createRole(body: SysRoleBody) {
  return api.post<{ id: number }>('/api/v1/system/role', body)
}

export function updateRole(roleId: number, body: SysRoleBody) {
  return api.put<{ ok: boolean }>(`/api/v1/system/role/${roleId}`, body)
}

export function assignRoleMenus(roleId: number, menuIds: number[]) {
  return api.put<{ ok: boolean }>(`/api/v1/system/role/${roleId}/menus`, { menu_ids: menuIds })
}

export function assignRoleDataScope(roleId: number, body: DataScopeBody) {
  return api.put<{ ok: boolean }>(`/api/v1/system/role/${roleId}/data-scope`, {
    data_scope: body.data_scope,
    dept_ids: body.dept_ids || [],
  })
}

export function changeRoleStatus(roleId: number, status: number) {
  return api.put<{ ok: boolean }>(`/api/v1/system/role/${roleId}/status`, { status })
}

export function deleteRole(roleId: number) {
  return api.delete<{ ok: boolean }>(`/api/v1/system/role/${roleId}`)
}

export function deleteRolesBatch(roleIds: number[]) {
  return api.delete<{ ok: boolean; deleted: number }>('/api/v1/system/role', { data: { role_ids: roleIds } })
}

// ---------- 菜单管理 ----------
export interface SysMenuBody {
  parent_id?: number
  menu_name: string
  i18n_key?: string | null
  path?: string | null
  component?: string | null
  menu_type: 'M' | 'C' | 'F'
  permission?: string | null
  icon?: string | null
  sort?: number
  visible?: number
  status?: number
  remark?: string | null
}

export function listMenus() {
  return api.get<MenuNode[]>('/api/v1/system/menu/list')
}

export function getMenu(menuId: number) {
  return api.get<MenuNode>(`/api/v1/system/menu/${menuId}`)
}

export function createMenu(body: SysMenuBody) {
  return api.post<{ id: number }>('/api/v1/system/menu', body)
}

export function updateMenu(menuId: number, body: SysMenuBody) {
  return api.put<{ ok: boolean }>(`/api/v1/system/menu/${menuId}`, body)
}

export function deleteMenu(menuId: number) {
  return api.delete<{ ok: boolean }>(`/api/v1/system/menu/${menuId}`)
}

// ---------- 操作日志 ----------
export interface OperLogRow {
  id: number
  title?: string
  business_type: number
  method?: string
  request_method?: string
  oper_url?: string
  oper_ip?: string
  oper_name?: string
  oper_param?: string | null
  json_result?: string | null
  status: number
  error_msg?: string | null
  oper_time?: string
}

export function listOperLogs(params: {
  title?: string
  oper_name?: string
  status?: number
  business_type?: number
  begin?: string
  end?: string
  offset?: number
  limit?: number
}) {
  return api.get<PageResult<OperLogRow>>('/api/v1/system/log/list', { params })
}

export function deleteOperLogs(ids: number[]) {
  return api.delete<{ ok: boolean; deleted: number }>('/api/v1/system/log', { data: { ids } })
}

export function cleanOperLogs() {
  return api.delete<{ ok: boolean; cleaned: number }>('/api/v1/system/log/clean')
}

// ---------- 部门管理 ----------
export interface SysDeptRow {
  dept_id: number
  parent_id: number
  ancestors?: string
  dept_name: string
  order_num: number
  leader?: string | null
  phone?: string | null
  email?: string | null
  status: string
  create_time?: string | null
  children?: SysDeptRow[]
}

export interface SysDeptBody {
  parent_id?: number
  dept_name: string
  order_num?: number
  leader?: string | null
  phone?: string | null
  email?: string | null
  status?: string
}

export function listDepts() {
  return api.get<SysDeptRow[]>('/api/v1/system/dept/list')
}

export function createDept(body: SysDeptBody) {
  return api.post<{ dept_id: number }>('/api/v1/system/dept', body)
}

export function updateDept(deptId: number, body: SysDeptBody) {
  return api.put<{ ok: boolean }>(`/api/v1/system/dept/${deptId}`, body)
}

export function deleteDept(deptId: number) {
  return api.delete<{ ok: boolean }>(`/api/v1/system/dept/${deptId}`)
}

// ---------- 岗位管理 ----------
export interface SysPostRow {
  post_id: number
  post_code: string
  post_name: string
  post_sort: number
  status: string
  create_time?: string | null
  remark?: string | null
}

export interface SysPostBody {
  post_code: string
  post_name: string
  post_sort?: number
  status?: string
  remark?: string | null
}

export function listPosts(params: {
  post_code?: string
  post_name?: string
  status?: string
  offset?: number
  limit?: number
}) {
  return api.get<PageResult<SysPostRow>>('/api/v1/system/post/list', { params })
}

export function listPostOptions() {
  return api.get<SysPostRow[]>('/api/v1/system/post/options')
}

export function createPost(body: SysPostBody) {
  return api.post<{ post_id: number }>('/api/v1/system/post', body)
}

export function updatePost(postId: number, body: SysPostBody) {
  return api.put<{ ok: boolean }>(`/api/v1/system/post/${postId}`, body)
}

export function deletePost(postId: number) {
  return api.delete<{ ok: boolean }>(`/api/v1/system/post/${postId}`)
}

// ---------- 登录日志 ----------
export interface LoginLogRow {
  info_id: number
  user_name?: string
  ipaddr?: string
  login_location?: string
  browser?: string
  os?: string
  status: string
  msg?: string
  login_time?: string
}

export function listLoginLogs(params: {
  user_name?: string
  status?: string
  begin?: string
  end?: string
  offset?: number
  limit?: number
}) {
  return api.get<PageResult<LoginLogRow>>('/api/v1/system/loginlog/list', { params })
}

export function deleteLoginLogs(ids: number[]) {
  return api.delete<{ ok: boolean; deleted: number }>('/api/v1/system/loginlog', { data: { ids } })
}

export function cleanLoginLogs() {
  return api.delete<{ ok: boolean; cleaned: number }>('/api/v1/system/loginlog/clean')
}

// ---------- 参数设置 ----------
export interface SysConfigRow {
  config_id: number
  config_name: string
  config_key: string
  config_value: string
  config_type: string
  create_time?: string | null
  remark?: string | null
}

export interface SysConfigBody {
  config_name: string
  config_key: string
  config_value: string
  config_type?: string
  remark?: string | null
}

export function listConfigs(params: {
  config_name?: string
  config_key?: string
  config_type?: string
  offset?: number
  limit?: number
}) {
  return api.get<PageResult<SysConfigRow>>('/api/v1/system/config/list', { params })
}

export function createConfig(body: SysConfigBody) {
  return api.post<{ config_id: number }>('/api/v1/system/config', body)
}

export function updateConfig(configId: number, body: SysConfigBody) {
  return api.put<{ ok: boolean }>(`/api/v1/system/config/${configId}`, body)
}

export function deleteConfig(configId: number) {
  return api.delete<{ ok: boolean }>(`/api/v1/system/config/${configId}`)
}

// ---------- 字典管理 ----------
export interface SysDictTypeRow {
  dict_id: number
  dict_name: string
  dict_type: string
  status: string
  create_time?: string | null
  remark?: string | null
}

export interface SysDictTypeBody {
  dict_name: string
  dict_type: string
  status?: string
  remark?: string | null
}

export interface SysDictDataRow {
  dict_code: number
  dict_sort: number
  dict_label: string
  dict_value: string
  dict_type: string
  css_class?: string | null
  list_class?: string | null
  is_default: string
  status: string
  create_time?: string | null
  remark?: string | null
}

export interface SysDictDataBody {
  dict_sort?: number
  dict_label: string
  dict_value: string
  dict_type: string
  css_class?: string | null
  list_class?: string | null
  is_default?: string
  status?: string
  remark?: string | null
}

export function listDictTypes(params: {
  dict_name?: string
  dict_type?: string
  status?: string
  offset?: number
  limit?: number
}) {
  return api.get<PageResult<SysDictTypeRow>>('/api/v1/system/dict/type/list', { params })
}

export function createDictType(body: SysDictTypeBody) {
  return api.post<{ dict_id: number }>('/api/v1/system/dict/type', body)
}

export function updateDictType(dictId: number, body: SysDictTypeBody) {
  return api.put<{ ok: boolean }>(`/api/v1/system/dict/type/${dictId}`, body)
}

export function deleteDictType(dictId: number) {
  return api.delete<{ ok: boolean }>(`/api/v1/system/dict/type/${dictId}`)
}

export function listDictData(params: {
  dict_type?: string
  dict_label?: string
  status?: string
  offset?: number
  limit?: number
}) {
  return api.get<PageResult<SysDictDataRow>>('/api/v1/system/dict/data/list', { params })
}

export function createDictData(body: SysDictDataBody) {
  return api.post<{ dict_code: number }>('/api/v1/system/dict/data', body)
}

export function updateDictData(dictCode: number, body: SysDictDataBody) {
  return api.put<{ ok: boolean }>(`/api/v1/system/dict/data/${dictCode}`, body)
}

export function deleteDictData(dictCode: number) {
  return api.delete<{ ok: boolean }>(`/api/v1/system/dict/data/${dictCode}`)
}

// ---------- 白名单设置 ----------
export interface WhitelistRow {
  id: number
  path: string
  path_type: string
  remark?: string | null
  status: string
  create_time?: string
  update_time?: string
}

export interface WhitelistBody {
  path: string
  path_type?: string
  remark?: string | null
  status?: string
}

export function listWhitelists(params: {
  keyword?: string
  path_type?: string
  offset?: number
  limit?: number
}) {
  return api.get<PageResult<WhitelistRow>>('/api/v1/system/whitelist/list', { params })
}

export function createWhitelist(body: WhitelistBody) {
  return api.post<{ id: number }>('/api/v1/system/whitelist', body)
}

export function updateWhitelist(id: number, body: WhitelistBody) {
  return api.put<{ ok: boolean }>(`/api/v1/system/whitelist/${id}`, body)
}

export function deleteWhitelist(id: number) {
  return api.delete<{ ok: boolean }>(`/api/v1/system/whitelist/${id}`)
}
