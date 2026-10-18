import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

// Dev server proxies /api to the FastAPI backend; in Docker, NGINX does the same.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'happy-dom',
    include: ['src/tests/**/*.test.ts'],
  },
})
