import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// shared/ is the data contract (sites, timelines, windows, grids, scores, routes).
// Serving it as the public folder makes fetch('/sites.json') work in dev and in the build.
export default defineConfig({
  plugins: [react()],
  publicDir: '../shared',
  server: { fs: { allow: ['..'] } },
})
