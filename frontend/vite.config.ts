import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'
import { createDevProxy } from './src/api/proxyConfig.js'

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  server: {
    proxy: createDevProxy(loadEnv(mode, process.cwd(), 'VITE_')),
  },
  preview: {
    proxy: createDevProxy(loadEnv(mode, process.cwd(), 'VITE_')),
  },
  test: {
    include: ['src/**/*.test.{ts,tsx}'],
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    maxWorkers: 4,
  },
}))
