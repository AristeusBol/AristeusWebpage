import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Servido bajo subpath /app (mismo-origen con el panel Aristeus para SSO).
  base: '/app/',
  // maplibre-gl trae su worker por URL relativa; excluirlo del pre-bundling de
  // esbuild evita el warning "maplibre-gl-worker.mjs ... incompatible" y fallos
  // de parseo de tiles en dev.
  optimizeDeps: {
    exclude: ['maplibre-gl'],
  },
  server: {
    port: 5173,
    // TEMPORAL pruebas túnel Quick Tunnel (revertir al terminar).
    allowedHosts: ['.trycloudflare.com'],
    proxy: {
      // Evita CORS en dev: el front llama a /api y Vite lo reenvía al backend.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // Las fotos de calibración cuelgan de /uploads (ver api.fotoUrl).
      '/uploads': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 5173,
  },
})
