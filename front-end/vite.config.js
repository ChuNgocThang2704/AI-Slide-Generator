import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/lecgen-api': {
        target: 'https://lecgen.aitc.vn',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/lecgen-api/, ''),
      }
    }
  }
})
