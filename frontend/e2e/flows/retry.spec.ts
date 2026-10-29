import { test, expect } from '../fixtures.js'
import { uploadMeeting, expectReady } from '../meeting.js'

test('Transient một lần: đếm ngược theo next_run_at rồi tự tới ready', async ({
  page,
}) => {
  const { job } = await uploadMeeting(page, 'E2E transient retry')
  const timer = page.getByRole('timer', { name: 'Thời gian chờ thử lại' })
  await expect(timer).toContainText(/Đang thử lại sau \d+ giây/)
  const response = await page.request.get(`/api/v1/jobs/${job.id}`)
  const retry = await response.json()
  expect(retry.status).toBe('retry_scheduled')
  expect(retry.next_run_at).toBeTruthy()
  const seconds = Number((await timer.innerText()).match(/\d+/)?.[0])
  expect(
    Math.abs(
      seconds - Math.ceil((Date.parse(retry.next_run_at) - Date.now()) / 1000),
    ),
  ).toBeLessThanOrEqual(2)
  await expect
    .poll(async () => Number((await timer.innerText()).match(/\d+/)?.[0]))
    .toBeLessThan(seconds)
  await expectReady(page)
  const done = await page.request.get(`/api/v1/jobs/${job.id}`)
  expect((await done.json()).attempt).toBe(2)
})
