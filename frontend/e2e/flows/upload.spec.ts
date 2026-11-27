import { test, expect } from '../fixtures.js'
import { readdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { uploadMeeting, expectReady } from '../meeting.js'

test('Upload có consent qua đủ sáu stage tới ready', async ({ page }) => {
  const { meeting, job } = await uploadMeeting(page, 'E2E upload ready')
  await page.getByRole('link', { name: 'Xem tiến độ' }).click()
  const stages = page
    .getByRole('region', { name: 'Tiến độ xử lý cuộc họp' })
    .getByRole('listitem')
  await expect(stages).toHaveCount(6)
  await expect(page.locator('[data-status="succeeded"]')).toBeVisible({
    timeout: 90_000,
  })
  await expect(page.locator('.job-stage[data-state="completed"]')).toHaveCount(
    6,
  )
  await page.reload()
  await expect(stages).toHaveCount(6)
  await page.getByRole('link', { name: 'Về nội dung cuộc họp' }).click()
  await expectReady(page)
  const result = await page.request.get(`/api/v1/meetings/${meeting.id}`)
  expect((await result.json()).status).toBe('ready')
  const processed = await page.request.get(`/api/v1/jobs/${job.id}`)
  expect(Object.values((await processed.json()).stages)).toEqual(
    Array(6).fill('succeeded'),
  )
})

test('RT-11: reload khi đang xử lý, tiếp tục job cũ và không tạo thêm job', async ({
  page,
}) => {
  let meetingPosts = 0
  let jobPosts = 0
  page.on('request', (request) => {
    if (request.method() !== 'POST') return
    if (new URL(request.url()).pathname === '/api/v1/meetings') meetingPosts++
    if (/\/meetings\/[^/]+\/jobs$/.test(request.url())) jobPosts++
  })
  const { meeting, job } = await uploadMeeting(page, 'E2E RT-11 reload')
  await expect(page.locator('[data-status="running"]')).toBeVisible()
  const progress = page.getByRole('progressbar', {
    name: 'Tiến độ xử lý',
    exact: true,
  })
  await expect(progress).toBeVisible()
  const running = await (
    await page.request.get(`/api/v1/jobs/${job.id}`)
  ).json()
  expect(
    Number(await progress.getAttribute('aria-valuenow')),
  ).toBeGreaterThanOrEqual(0)
  expect(running.progress).toBeLessThanOrEqual(1)
  await page.reload()
  await expect(
    page.getByRole('region', { name: 'Tiến độ xử lý cuộc họp' }),
  ).toBeVisible()
  await expectReady(page)
  const persisted = await page.request.get(`/api/v1/meetings/${meeting.id}`)
  expect((await persisted.json()).latest_job_id).toBe(job.id)
  expect(meetingPosts).toBe(1)
  expect(jobPosts).toBe(0)
})

// Đọc trước khi stack dừng; harness kiểm thư mục này đã được xóa sau khi Playwright thoát.
test.afterAll(async ({ browserName }, info) => {
  const storage = process.env.E2E_STORAGE_DIR
  expect(storage).toBeTruthy()
  if (!storage) throw new Error('Thiếu E2E_STORAGE_DIR của stack.')
  const directories = async (name: string) =>
    (await readdir(path.join(storage, name), { withFileTypes: true })).filter(
      (entry) => entry.isDirectory(),
    ).length
  const result = {
    browser: browserName,
    storageExists: true,
    audio: await directories('audio'),
    artifacts: await directories('artifacts'),
  }
  expect(result.audio).toBeGreaterThan(0)
  expect(result.artifacts).toBeGreaterThan(0)
  await writeFile(
    info.outputPath('upload-storage-result.json'),
    JSON.stringify(result, null, 2) + '\n',
    'utf8',
  )
})
