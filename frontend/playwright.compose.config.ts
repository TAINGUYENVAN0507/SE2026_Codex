import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e/compose',
  testMatch: 'web.spec.ts',
  workers: 1,
  retries: 0,
  forbidOnly: Boolean(process.env.CI),
  timeout: 120_000,
  expect: { timeout: 20_000 },
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report/compose', open: 'never' }],
  ],
  outputDir: 'test-results/compose',
  use: {
    ...devices['Desktop Chrome'],
    baseURL: process.env.COMPOSE_E2E_BASE_URL || 'http://localhost:8080',
    serviceWorkers: 'block',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
})
