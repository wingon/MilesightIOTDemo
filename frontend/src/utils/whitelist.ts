import { getFrontWhitelist } from '@/api/auth'

let cached: string[] | null = null
let pending: Promise<string[]> | null = null

/** 确保前端路由白名单已加载（公开接口，未登录也可调用）。结果缓存。 */
export function ensureWhitelist(): Promise<string[]> {
  if (cached) return Promise.resolve(cached)
  if (!pending) {
    pending = getFrontWhitelist()
      .then((res) => {
        cached = res.data || []
        return cached
      })
      .catch(() => {
        cached = []
        return cached
      })
  }
  return pending
}

/** 判断路径是否命中白名单前缀（前缀匹配，含子路径，如 /building-viewer/floor/2） */
export function isWhitelistedPath(path: string): boolean {
  const list = cached || []
  return list.some((p) => p && (path === p || path.startsWith(`${p}/`)))
}

/** 手动刷新白名单（管理界面增删后调用） */
export function resetWhitelistCache() {
  cached = null
  pending = null
}
