import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// /api/* is proxied to FastAPI in dev, so the browser never deals with CORS locally.
// In AWS (Phase 14) CloudFront routes /api/* to API Gateway the same way.
const apiTarget = process.env.API_URL ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    proxy: { '/api': { target: apiTarget, rewrite: (p) => p.replace(/^\/api/, '') } },
  },
})
