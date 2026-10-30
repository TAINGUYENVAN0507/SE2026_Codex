import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  testDir: '.',
  testMatch: 'autosave.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 20000,
  reporter: [
    ['list'],
    [
      'json',
      {
        outputFile: fileURLToPath(
          new URL('./evidence/e2e.json', import.meta.url),
        ),
      },
    ],
  ],
  use: {
    baseURL: 'http://127.0.0.1:14174',
    browserName: 'chromium',
    serviceWorkers: 'block',
  },
  webServer: {
    cwd: fileURLToPath(new URL('../', import.meta.url)),
    command:
      'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 14174 --strictPort',
    url: 'http://127.0.0.1:14174',
    reuseExistingServer: false,
    env: { VITE_API_MOCK: '0' },
  },
})
