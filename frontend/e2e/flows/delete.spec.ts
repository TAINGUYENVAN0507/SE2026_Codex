import { test, expect } from '../fixtures.js'
import { uploadMeeting } from '../meeting.js'

test('RT-15/PRIV-13: xóa cuộc họp lúc job đang chạy và không truy cập lại được', async ({
  page,
}) => {
  const { meeting, job } = await uploadMeeting(page, 'E2E xóa khi đang xử lý')
  await expect(page.locator('[data-status="running"]')).toBeVisible()
  await page.getByRole('button', { name: 'Xóa cuộc họp', exact: true }).click()
  const confirm = page.getByRole('alertdialog', { name: 'Xóa cuộc họp?' })
  await expect(confirm).toContainText('lịch sử chỉnh sửa')
  const deleted = page.waitForResponse(
    (r) =>
      r.request().method() === 'DELETE' &&
      r.url().endsWith(`/meetings/${meeting.id}`),
  )
  await confirm.getByRole('button', { name: 'Xóa vĩnh viễn' }).click()
  expect((await deleted).status()).toBe(204)
  await expect(page).toHaveURL(/\/meetings$/)
  expect(
    (await page.request.get(`/api/v1/meetings/${meeting.id}`)).status(),
  ).toBe(404)
  expect(
    (await page.request.get(`/api/v1/meetings/${meeting.id}/audio`)).status(),
  ).toBe(404)
  expect((await page.request.get(`/api/v1/jobs/${job.id}`)).status()).toBe(404)
  await page.goto(`/meetings/${meeting.id}`)
  await expect(
    page.getByRole('heading', { name: 'Không tìm thấy cuộc họp' }),
  ).toBeVisible()
})
