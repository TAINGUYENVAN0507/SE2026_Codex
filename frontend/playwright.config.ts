import { defineConfig, devices } from '@playwright/test'

const scenario = process.env.FAKE_SCENARIO || 'slow'
const cases: Record<string, string[]> = {
  slow: ['flows/login.spec.ts', 'flows/upload.spec.ts', 'privacy/*.spec.ts'],
  permanent: ['flows/permanent.spec.ts'],
  transient_once: ['flows/retry.spec.ts'],
  summary_fail: ['flows/partial.spec.ts'],
}
if (!cases[scenario]) throw new Error(`Kịch bản E2E không hợp lệ: ${scenario}`)

export default defineConfig({
  testDir: './e2e',
  testMatch: cases[scenario],
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 20_000 },
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:14173',
    serviceWorkers: 'block',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    permissions: ['microphone'],
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: {
          args: [
            '--use-fake-device-for-media-stream',
            '--use-fake-ui-for-media-stream',
          ],
        },
      },
    },
  ],
  webServer: {
    command:
      process.platform === 'win32'
        ? 'node e2e/stack.mjs'
        : 'bash e2e/start-stack.sh',
    url: 'http://127.0.0.1:14173/api/v1/health',
    reuseExistingServer: false,
    timeout: 180_000,
    gracefulShutdown: { signal: 'SIGTERM', timeout: 10_000 },
  },
})
