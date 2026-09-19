import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import react from '@astrojs/react';

export default defineConfig({
  integrations: [
    tailwind({
      applyBaseStyles: false
    }),
    react()
  ],
  output: 'static',
  build: {
    format: 'directory'
  },
  vite: {
    resolve: {
      alias: {
        '@': '/src'
      }
    },
    ssr: {
      noExternal: ['react-leaflet', 'leaflet']
    },
    server: {
      // TEMPORAL pruebas túnel Quick Tunnel (revertir al terminar).
      allowedHosts: ['.trycloudflare.com'],
      proxy: {
        // App GrassGauge bajo mismo origen para SSO.
        '/app': {
          target: 'http://localhost:5173',
          changeOrigin: true,
          ws: true,
        },
        // API GrassGauge para la app servida por este origen.
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
        '/health': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
        '/uploads': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  }
});
