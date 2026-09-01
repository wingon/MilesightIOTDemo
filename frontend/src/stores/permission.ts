import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { RouteRecordRaw } from 'vue-router'
import router from '@/router'
import { getUserRoutes, type MenuNode } from '@/api/auth'

// 预收集 src/views 下全部 .vue 组件，供动态路由按 component 字段懒加载
const viewModules = import.meta.glob('@/views/**/*.vue')

function resolveView(component?: string | null) {
  if (!component) return undefined
  return viewModules[`/src/views/${component}.vue`]
}

export const usePermissionStore = defineStore('permission', () => {
  /** 后端菜单树（MainLayout 据此渲染侧边栏） */
  const menuTree = ref<MenuNode[]>([])
  /** 是否已把动态路由注册进 router */
  const routesLoaded = ref(false)

  /**
   * 拉取当前用户菜单并注册为 'root'（MainLayout）下的子路由。
   * - C 菜单：注册可导航路由（component 懒加载）
   * - M 目录：有 path 作为分组路由；path 为空则打平其子级
   * - F 按钮：仅用于权限标识，不生成路由
   */
  function collectRoutes(menus: MenuNode[]): RouteRecordRaw[] {
    const result: RouteRecordRaw[] = []
    for (const menu of menus) {
      if (menu.menu_type === 'F') continue
      const children = menu.children?.length ? collectRoutes(menu.children) : []
      const meta = {
        titleKey: (menu.i18n_key || undefined) as string | undefined,
        menuName: menu.menu_name,
      }
      if (menu.menu_type === 'C' && menu.component) {
        result.push({
          path: menu.path === '/' ? '' : menu.path || '',
          name: `menu-${menu.id}`,
          component: resolveView(menu.component),
          meta,
          children: children.length ? children : undefined,
        } as RouteRecordRaw)
      } else if (menu.path) {
        result.push({ path: menu.path, name: `menu-${menu.id}`, children } as RouteRecordRaw)
      } else {
        result.push(...children)
      }
    }
    return result
  }

  async function generateRoutes() {
    const res = await getUserRoutes()
    menuTree.value = res.data
    const routes = collectRoutes(res.data)
    routes.forEach((route) => router.addRoute('root', route))
    routesLoaded.value = true
  }

  function reset() {
    menuTree.value = []
    routesLoaded.value = false
  }

  return { menuTree, routesLoaded, generateRoutes, collectRoutes, reset }
})
