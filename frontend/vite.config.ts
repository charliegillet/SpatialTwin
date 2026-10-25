import { resolve } from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // dev only: the FastAPI backend serves frontend/dist itself on :8000
  server: { host: true, proxy: { '/api': 'http://localhost:8000' } },
  build: {
    rollupOptions: {
      input: {
        main: resolve(import.meta.dirname, 'index.html'),
        render: resolve(import.meta.dirname, 'render.html'),
      },
    },
  },
})
