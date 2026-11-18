import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import path from 'node:path'

export default defineConfig({
  plugins: [
    vue(),
    AutoImport({ resolvers: [ElementPlusResolver()] }),
    Components({ resolvers: [ElementPlusResolver()] }),
  ],
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/user': { target: 'http://localhost:9080', changeOrigin: true },
      '/admin': { target: 'http://localhost:9080', changeOrigin: true },
      // 公告端点逐一登记代理：/notice 前缀整体代理会与 Vue 路由 /notice 冲突（直接访问/刷新显示网关 401 JSON）
      '/notice/getList': { target: 'http://localhost:9080', changeOrigin: true },
      '/notice/get': { target: 'http://localhost:9080', changeOrigin: true },
      '/notice/add': { target: 'http://localhost:9080', changeOrigin: true },
      '/notice/delete': { target: 'http://localhost:9080', changeOrigin: true },
      '/notice/update': { target: 'http://localhost:9080', changeOrigin: true },
      '/agent': { target: 'http://localhost:9080', changeOrigin: true },
      // /ai 前缀与 Vue 路由 /ai 冲突：后端 /ai/** 若新增前端调用方，须在此逐端点登记
      // agent 管理面 API（审核/成本/审计）直达 8000，不走网关
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      // 发帖实时推送 STOMP（SockJS 端点的原生 WebSocket 通道）
      '/ws': { target: 'http://localhost:9080', changeOrigin: true, ws: true },
    },
  },
})