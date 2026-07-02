// 文件路径：frontend/vite.config.ts
// 文件作用：Vite 配置，含开发时代理转发到后端
// 最后更新时间：2026-06-28-2016
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 开发时后端地址
const BACKEND = process.env.VITE_BACKEND || 'http://127.0.0.1:8765'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
      '/screenshots': { target: BACKEND, changeOrigin: true },
    },
  },
})
