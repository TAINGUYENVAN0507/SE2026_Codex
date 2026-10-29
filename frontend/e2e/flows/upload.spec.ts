import { test, expect } from '../fixtures.js'
import { uploadMeeting, expectReady } from '../meeting.js'

test('Upload có consent qua đủ sáu stage tới ready', async ({ page }) => {
  const { meeting, job } = await uploadMeeting(page, 'E2E upload ready')
  const stages = page
    .getByRole('region', { name: 'Tiến độ xử lý cuộc họp' })
    .getByRole('listitem')
  await expect(stages).toHaveCount(6)
  await expectReady(page)
  await expect(page.locator('.job-stage[data-state="completed"]')).toHaveCount(
    6,
  )
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
