import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'
import { readFileSync } from 'node:fs'
import { createDevProxy } from './src/api/proxyConfig.js'

// FE-19: chỉ bật thao tác xóa khi contract của B đã công bố endpoint.
const apiContract = JSON.parse(
  readFileSync(new URL('../contracts/openapi.json', import.meta.url), 'utf8'),
) as { paths?: Record<string, { delete?: unknown }> }

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  define: {
    __ACCOUNT_DELETION_AVAILABLE__: JSON.stringify(
      Boolean(apiContract.paths?.['/api/v1/auth/me']?.delete),
    ),
  },
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
    coverage: {
      provider: 'v8',
      reporter: ['text-summary', 'json-summary', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/test/**',
        'src/mocks/**',
        'src/api/schema.d.ts',
      ],
      thresholds: { lines: 84.5, branches: 78.75 },
    },
    maxWorkers: 4,
  },
}))
