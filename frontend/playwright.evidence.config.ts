import { defineConfig } from '@playwright/test'
import base from './playwright.config.js'

const server = base.webServer
if (!server || Array.isArray(server))
  throw new Error('Cần một stack E2E riêng.')

export default defineConfig({
  ...base,
  testMatch: ['evidence/progress.spec.ts'],
  timeout: 180_000,
  projects: base.projects?.map((project) => ({
    ...project,
    use: { ...project.use, viewport: { width: 1440, height: 1000 } },
  })),
  webServer: {
    ...server,
    env: { ...server.env, E2E_MANUAL_WORKER: '1' },
  },
})
