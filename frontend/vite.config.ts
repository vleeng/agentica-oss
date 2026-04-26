import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/agentica/',
  plugins: [react()],
  server: {
    port: 5173,
    allowedHosts: ['vleeng.com', 'localhost'],
    proxy: {
      // El Vite dev server reenvía /api al backend container (red Docker interna)
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
        ws: true,   // también proxea WebSockets (/api/v1/agents/{id}/ws)
      },
    },
  },
})
