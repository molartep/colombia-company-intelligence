import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          // Cache the shared UI runtime independently from changing application code.
          if (
            /node_modules\/(?:react|react-dom|scheduler|react-router|react-router-dom)\//.test(id)
          )
            return 'react-vendor'
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': process.env.API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
      '/health': process.env.API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    globals: true,
    restoreMocks: true,
  },
})
