import { test, expect } from '../fixtures.js'
import { uploadMeeting } from '../meeting.js'

test('Lỗi permanent hiển thị tiếng Việt theo code, không lộ message kỹ thuật', async ({
  page,
}) => {
  const { meeting } = await uploadMeeting(page, 'E2E permanent error')
  const progress = page.getByRole('region', { name: 'Tiến độ xử lý cuộc họp' })
  await expect(progress.getByRole('status')).toHaveText('Xử lý thất bại')
  await expect(progress.getByRole('alert')).toHaveText(
    'File audio không hợp lệ hoặc không thể đọc.',
  )
  await expect(page.locator('body')).not.toContainText(
    'fake: file không decode được',
  )
  const response = await page.request.get(`/api/v1/meetings/${meeting.id}`)
  expect((await response.json()).status).toBe('failed')
})
