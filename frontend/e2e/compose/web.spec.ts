import { test, expect } from '@playwright/test'
import { readFile } from 'node:fs/promises'

import { syntheticWav } from '../audio.js'

test('BE-16: đăng nhập, upload, xử lý và export đi qua nginx thật', async ({
  page,
  baseURL,
}) => {
  const password = process.env.COMPOSE_E2E_PASSWORD
  if (!password) throw new Error('Thiếu COMPOSE_E2E_PASSWORD')
  const apiOrigins = new Set<string>()
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/api/'))
      apiOrigins.add(new URL(request.url()).origin)
  })
  const response = await page.goto('/login')
  expect(response?.headers()['server']).toMatch(/nginx/i)
  await page
    .getByLabel('Email', { exact: true })
    .fill(process.env.COMPOSE_E2E_EMAIL || 'compose-e2e@example.local')
  await page.getByLabel('Mật khẩu', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  await expect(page).toHaveURL(/\/meetings$/)
  await page
    .getByRole('link', { name: /Cuộc họp mới/ })
    .first()
    .click()
  await page.getByLabel('Chọn file audio').setInputFiles(syntheticWav(30))
  await page
    .getByRole('checkbox', { name: /Tôi xác nhận đã có sự đồng ý/ })
    .check()
  await page.getByRole('button', { name: 'Tạo biên bản' }).click()
  await expect(page).toHaveURL(/\/meetings\/[0-9a-f-]+$/)
  const meetingId = new URL(page.url()).pathname.split('/').pop()!
  try {
    await expect
      .poll(
        async () => {
          const result = await page.request.get(`/api/v1/meetings/${meetingId}`)
          expect(result.status()).toBe(200)
          return (await result.json()).status
        },
        { timeout: 90_000 },
      )
      .toBe('ready')
    const exportButton = page.getByRole('button', {
      name: 'Xuất biên bản',
      exact: true,
    })
    await expect(exportButton).toBeEnabled()
    await exportButton.click()
    const downloadPromise = page.waitForEvent('download')
    await page
      .getByRole('button', { name: 'Dữ liệu (.json)', exact: true })
      .click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toMatch(/\.json$/)
    const exported = JSON.parse(
      await readFile((await download.path())!, 'utf8'),
    )
    expect(exported.schema_version).toBe('1.1')
    expect(exported.meeting.id).toBe(meetingId)
    expect(exported.segments.length).toBeGreaterThan(0)
    expect([...apiOrigins]).toEqual([new URL(baseURL!).origin])
  } finally {
    // Chỉ xóa meeting tổng hợp vừa được test tạo trong stack riêng.
    const deleted = await page.request.delete(`/api/v1/meetings/${meetingId}`)
    expect(deleted.status()).toBe(204)
  }
})
