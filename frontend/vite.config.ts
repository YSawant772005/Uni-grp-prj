import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

// Dev server proxies /api to the FastAPI backend; in Docker, NGINX does the same.
// VITE_PROXY_TARGET lets the dev container reach the `api` service by name.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'happy-dom',
    include: ['src/tests/**/*.test.ts'],
  },
})
