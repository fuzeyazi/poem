import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import App from './App.vue'
import router from './router'
import { vReveal } from './directives/reveal'
import { useTheme } from './composables/useTheme'
import '@fontsource/noto-serif-sc/500.css'
import '@fontsource/noto-serif-sc/600.css'
import '@fontsource/noto-serif-sc/900.css'
import '@fontsource/noto-sans-sc/300.css'
import '@fontsource/noto-sans-sc/400.css'
import '@fontsource/noto-sans-sc/500.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
// 手动 import 的 ElMessage 不走 unplugin 按需样式，需显式引入其样式（否则 toast 裸渲染在角落）
import 'element-plus/es/components/message/style/css'
import './assets/main.css'
import './assets/material3.css'

useTheme()
const app = createApp(App)
const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)
app.use(pinia)
app.use(router)
app.directive('reveal', vReveal)
app.mount('#app')
