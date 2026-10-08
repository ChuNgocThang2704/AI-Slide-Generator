import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  build: {
    // The production bundle discards console.* calls: several of them print auth
    // tokens and whole API responses, which would otherwise be visible in F12.
    // Real failures still surface through the network tab and error boundaries.
    rolldownOptions: mode === 'production'
      ? { output: { minify: { compress: { dropConsole: true, dropDebugger: true }, mangle: true, codegen: true } } }
      : {},
  },
}))
