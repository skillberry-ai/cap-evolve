/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: proxy /api to the FastAPI backend. Build: emit to dist/ so the backend's
// resolve_static_dir() (dashboard/frontend/dist) serves it in production.
//
// Static export build (VITE_STATIC=1): emit with a RELATIVE base ('./') so the SPA
// can be served from any subpath / static host (python -m http.server, GitHub Pages).
// The live build keeps the default absolute base ('/').
const STATIC = process.env.VITE_STATIC === '1'

export default defineConfig({
  base: STATIC ? './' : '/',
  plugins: [react()],
  build: { outDir: 'dist' },
  server: {
    proxy: {
      '/api': {
        // Override with CAPEVOLVE_API=http://127.0.0.1:<port> to point `npm run dev`
        // at a backend on a non-default port (e.g. two runs open side by side).
        target: process.env.CAPEVOLVE_API || 'http://127.0.0.1:7878',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
