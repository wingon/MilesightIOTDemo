import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'
import i18n from '@/i18n'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: MainLayout,
      children: [
        {
          path: '',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
          meta: { titleKey: 'menu.dashboard' },
        },
        {
          path: 'ct103',
          name: 'ct103',
          component: () => import('@/views/TofListView.vue'),
          meta: { titleKey: 'menu.tof' },
        },
        {
          path: 'tof',
          redirect: '/ct103',
        },
        {
          path: 'ug65',
          name: 'ug65',
          component: () => import('@/views/Ug65ListView.vue'),
          meta: { titleKey: 'menu.ug65' },
        },
        {
          path: 'vs135',
          name: 'vs135',
          component: () => import('@/views/Vs135ListView.vue'),
          meta: { titleKey: 'menu.vs135' },
        },
        {
          path: 'building-viewer',
          name: 'building-viewer',
          component: () => import('@/views/BuildingViewerView.vue'),
          meta: { titleKey: 'menu.buildingViewer' },
        },
        {
          // 旧版楼宇检视（格子化外观），保留以利将来切换回来
          path: 'building-viewer-old',
          name: 'building-viewer-old',
          component: () => import('@/views/BuildingViewerOldView.vue'),
          meta: { titleKey: 'menu.buildingViewer' },
        },
        {
          path: 'people-count',
          name: 'people-count',
          component: () => import('@/views/PeopleCountListView.vue'),
          meta: { titleKey: 'menu.peopleCount' },
        },
        {
          path: 'building-viewer/floor/:floor',
          name: 'floor-viewer',
          component: () => import('@/views/FloorViewerView.vue'),
          meta: { titleKey: 'building.floorRouteTitle' },
        },
        {
          // 旧版地址兼容重定向
          path: 'building-facade-demo',
          redirect: '/building-viewer',
        },
        {
          path: 'devices',
          name: 'devices',
          component: () => import('@/views/DevicesManageView.vue'),
          meta: { titleKey: 'menu.devices' },
        },
      ],
    },
  ],
})

router.afterEach((to) => {
  const key = to.meta.titleKey as string | undefined
  const pageTitle = key ? String(i18n.global.t(key)) : String(i18n.global.t('common.brand'))
  document.title = `${pageTitle} · ${String(i18n.global.t('common.brand'))}`
})

export default router
