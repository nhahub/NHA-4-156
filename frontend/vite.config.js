import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // Proxy API + auth routes to the FastAPI backend in local dev.
      // In production (Docker) everything is same-origin on one port, so
      // this proxy is never used.
      '/repos': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
    },
  },
})
