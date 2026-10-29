import { test, expect, type Page } from '@playwright/test'
import { login } from '../fixtures.js'

declare global {
  interface Window {
    recorderProbe: { calls: number; tracks: MediaStreamTrack[]; deny: boolean }
  }
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.recorderProbe = { calls: 0, tracks: [], deny: false }
    const native = navigator.mediaDevices.getUserMedia.bind(
      navigator.mediaDevices,
    )
    navigator.mediaDevices.getUserMedia = async (constraints) => {
      window.recorderProbe.calls++
      if (window.recorderProbe.deny)
        throw new DOMException('Test denial', 'NotAllowedError')
      const stream = await native(constraints)
      window.recorderProbe.tracks.push(...stream.getTracks())
      return stream
    }
  })
  await login(page)
})

async function recorder(page: Page) {
  await page.goto('/meetings/new')
  await page.getByRole('button', { name: 'Ghi âm', exact: true }).click()
}
async function start(page: Page) {
  await recorder(page)
  await page.getByRole('checkbox').check()
  await page
    .getByRole('button', { name: 'Bắt đầu ghi âm', exact: true })
    .click()
  await expect(page.getByRole('status')).toContainText('Đang ghi âm', {
    timeout: 1_000,
  })
}
async function stopped(page: Page) {
  await expect
    .poll(() =>
      page.evaluate(() =>
        window.recorderProbe.tracks.map((track) => track.readyState),
      ),
    )
    .toEqual(['ended'])
}
function uploads(page: Page) {
  const requests: string[] = []
  page.on('request', (r) => {
    if (
      r.method() === 'POST' &&
      new URL(r.url()).pathname === '/api/v1/meetings'
    )
      requests.push(r.url())
  })
  return requests
}

test('PRIV-01: mở app và chuyển trang không tự xin micro', async ({ page }) => {
  await recorder(page)
  await expect(
    page.getByRole('button', { name: 'Bắt đầu ghi âm' }),
  ).toBeVisible()
  expect(await page.evaluate(() => window.recorderProbe.calls)).toBe(0)
  await page.getByRole('link', { name: 'Hủy', exact: true }).click()
  await expect(page).toHaveURL(/\/meetings$/)
  expect(await page.evaluate(() => window.recorderProbe.calls)).toBe(0)
})

test('PRIV-02: chưa consent thì nút bắt đầu bị khóa và không gọi micro', async ({
  page,
}) => {
  await recorder(page)
  await expect(
    page.getByRole('button', { name: 'Bắt đầu ghi âm' }),
  ).toBeDisabled()
  expect(await page.evaluate(() => window.recorderProbe.calls)).toBe(0)
})

test('PRIV-03: click bắt đầu chỉ gọi micro một lần, hiện indicator và timer', async ({
  page,
}) => {
  await start(page)
  expect(await page.evaluate(() => window.recorderProbe.calls)).toBe(1)
  await expect(page.locator('.recorder-panel.recording')).toBeVisible()
  await expect(page.locator('.recorder-time')).not.toHaveText('00:00')
  await expect(page.getByRole('status')).toHaveAttribute('role', 'status')
})

test('PRIV-04: dừng ghi âm kết thúc mọi track và tắt indicator', async ({
  page,
}) => {
  await start(page)
  await expect(page.locator('.recorder-time')).not.toHaveText('00:00')
  await page.getByRole('button', { name: 'Dừng ghi âm' }).click()
  await stopped(page)
  await expect(page.locator('.recorder-panel.recording')).toHaveCount(0)
  await expect(page.getByText('Nghe thử trên máy · chưa tải lên')).toBeVisible()
})

test('PRIV-05: hủy bỏ bản ghi, dừng track, không gửi meeting', async ({
  page,
}) => {
  const requests = uploads(page)
  await start(page)
  await expect(page.locator('.recorder-time')).not.toHaveText('00:00')
  await page.getByRole('button', { name: 'Dừng ghi âm' }).click()
  await expect(page.getByText('Nghe thử trên máy · chưa tải lên')).toBeVisible()
  await page.getByRole('link', { name: 'Hủy', exact: true }).click()
  await expect(page).toHaveURL(/\/meetings$/)
  await stopped(page)
  await recorder(page)
  await expect(page.getByText('Nghe thử trên máy · chưa tải lên')).toHaveCount(
    0,
  )
  expect(requests).toHaveLength(0)
})

test('PRIV-06: chỉ upload sau click tạo biên bản và đúng một request', async ({
  page,
}) => {
  const requests = uploads(page)
  await start(page)
  await expect(page.locator('.recorder-time')).not.toHaveText('00:00')
  await page.getByRole('button', { name: 'Dừng ghi âm' }).click()
  await expect(page.getByText('Nghe thử trên máy · chưa tải lên')).toBeVisible()
  await stopped(page)
  expect(requests).toHaveLength(0)
  await page
    .getByRole('textbox', { name: 'Tên cuộc họp' })
    .fill('E2E consent recorder')
  const created = page.waitForResponse(
    (r) =>
      r.request().method() === 'POST' &&
      new URL(r.url()).pathname === '/api/v1/meetings',
  )
  await page.getByRole('button', { name: 'Tạo biên bản', exact: true }).click()
  expect((await created).status()).toBe(201)
  await expect(page).toHaveURL(/\/meetings\/[0-9a-f-]+$/)
  expect(requests).toHaveLength(1)
})

test('PRIV-07: reload lúc ghi có cảnh báo, không tự ghi lại hay upload', async ({
  page,
}) => {
  const requests = uploads(page)
  await start(page)
  let warning = false
  page.once('dialog', async (dialog) => {
    expect(dialog.type()).toBe('beforeunload')
    warning = true
    await dialog.accept()
  })
  await page.reload()
  await page.getByRole('button', { name: 'Ghi âm', exact: true }).click()
  await expect(
    page.getByRole('button', { name: 'Bắt đầu ghi âm' }),
  ).toBeDisabled()
  expect(warning).toBe(true)
  expect(await page.evaluate(() => window.recorderProbe.calls)).toBe(0)
  expect(requests).toHaveLength(0)
})

test('PRIV-08: từ chối micro hiện hướng dẫn và không tự xin lại', async ({
  page,
}) => {
  await recorder(page)
  await page.evaluate(() => {
    window.recorderProbe.deny = true
  })
  await page.getByRole('checkbox').check()
  await page
    .getByRole('button', { name: 'Bắt đầu ghi âm', exact: true })
    .click()
  await expect(page.getByRole('alert')).toHaveText(
    'Không truy cập được micro. Kiểm tra quyền micro hoặc chọn tải file audio.',
  )
  await page
    .getByRole('button', { name: 'Tải file audio', exact: true })
    .click()
  await expect(
    page.getByRole('button', { name: 'Chọn file trên máy' }),
  ).toBeVisible()
  expect(await page.evaluate(() => window.recorderProbe.calls)).toBe(1)
})

test('PRIV-09: điều hướng khỏi recorder dừng mọi track', async ({ page }) => {
  await start(page)
  await page.getByRole('link', { name: 'Hủy', exact: true }).click()
  await expect(page).toHaveURL(/\/meetings$/)
  await stopped(page)
})
