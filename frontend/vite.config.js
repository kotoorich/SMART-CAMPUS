import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Allow the containerised preview/proxy hosts used during development.
    allowedHosts: [".all-hands.dev", "localhost", "127.0.0.1"],
  },
})
