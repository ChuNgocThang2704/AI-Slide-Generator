import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ command }) => ({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/generate': 'http://localhost:8000',
      '/api': 'http://localhost:8000',
      '/outputs': 'http://localhost:8000',
    }
  },
  build: {
    outDir: '../public',
    emptyOutDir: true,
  },
  // dev: '/'  |  production (served by FastAPI at /ui): '/ui/'
  base: command === 'build' ? '/ui/' : '/',
}))
