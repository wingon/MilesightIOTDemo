import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'
import i18n from '@/i18n'
import { useUserStore } from '@/stores/user'
import { usePermissionStore } from '@/stores/permission'
import { ensureWhitelist, isWhitelistedPath } from '@/utils/whitelist'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { titleKey: 'login.title' },
    },
    {
      path: '/',
      name: 'root',
      component: MainLayout,
      children: [
        // 楼宇可视化：正常模式走 MainLayout（有 sidebar + header + tabs），
        // 大屏模式（?ls=）由 MainLayout 内部隐藏 chrome
        {
          path: 'building-viewer',
          name: 'building-viewer',
          component: () => import('@/views/BuildingViewerView.vue'),
          meta: { titleKey: 'menu.buildingViewer' },
        },
        // 楼栋楼层视图
        {
          path: 'building-viewer/floor/:floor',
          name: 'floor-viewer',
          component: () => import('@/views/FloorViewerView.vue'),
          meta: { titleKey: 'building.floorRouteTitle' },
        },
        // 个人中心
        {
          path: 'profile',
          name: 'profile',
          component: () => import('@/views/ProfileView.vue'),
          meta: { titleKey: 'profile.title' },
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue'),
    },
  ],
})

router.afterEach((to) => {
  const key = to.meta.titleKey as string | undefined
  const pageTitle = key ? String(i18n.global.t(key)) : String(i18n.global.t('common.brand'))
  document.title = `${pageTitle} · ${String(i18n.global.t('common.brand'))}`
})

router.beforeEach(async (to) => {
  const userStore = useUserStore()
  const permissionStore = usePermissionStore()

  // 登录页：已登录则回首页
  if (to.path === '/login') {
    if (userStore.token) return { path: '/' }
    return true
  }

  // 未登录：先检查是否命中白名单（大屏等免登录路径），命中则直接放行
  if (!userStore.token) {
    await ensureWhitelist()
    if (isWhitelistedPath(to.path)) return true
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  // 已登录但动态路由未加载：拉取用户信息 + 菜单并重新导航
  if (!permissionStore.routesLoaded) {
    try {
      await userStore.fetchUserInfo()
      await permissionStore.generateRoutes()
      // 用 fullPath 重新导航（不能用 {...to}，其 name 可能是 catch-all 的 not-found，
      // 会导致重导航时 name 优先匹配 404）
      return { path: to.fullPath, replace: true }
    } catch {
      userStore.reset()
      permissionStore.reset()
      return { path: '/login' }
    }
  }

  return true
})

export default router
