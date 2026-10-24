import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'
import { createDevProxy } from './src/api/proxyConfig.js'

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  server: {
    proxy: createDevProxy(loadEnv(mode, process.cwd(), 'VITE_')),
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
}))
