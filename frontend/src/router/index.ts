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
          path: 'building-viewer/floor/:floor',
          name: 'floor-viewer',
          component: () => import('@/views/FloorViewerView.vue'),
          meta: { titleKey: 'building.floorRouteTitle' },
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
  const pageTitle = key ? String(i18n.global.t(key)) : '333 IOT Console'
  document.title = `${pageTitle} · 333 IOT Console`
})

export default router
