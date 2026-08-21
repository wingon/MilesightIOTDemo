import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Antd from 'ant-design-vue'
import 'ant-design-vue/dist/reset.css'
import App from './App.vue'
import router from './router'
import i18n from './i18n'
import { useAppStore } from './stores/app'
import './styles/global.less'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(i18n)
app.use(Antd)

// 在挂载前应用大屏模式（URL ?ls=<scale>），避免页面闪烁
useAppStore().applyLargeScreenMode()

app.mount('#app')
