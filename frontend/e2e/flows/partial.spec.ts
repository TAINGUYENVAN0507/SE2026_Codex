import { test, expect } from '../fixtures.js'
import { uploadMeeting } from '../meeting.js'

test('Summary lỗi: partial vẫn đọc, sửa và lưu transcript thật', async ({
  page,
}) => {
  const { meeting } = await uploadMeeting(page, 'E2E partial transcript')
  await expect(
    page
      .getByRole('region', { name: 'Tiến độ xử lý cuộc họp' })
      .getByRole('status'),
  ).toHaveText('Xử lý thất bại')
  await expect
    .poll(
      async () =>
        (
          await (
            await page.request.get(`/api/v1/meetings/${meeting.id}`)
          ).json()
        ).status,
    )
    .toBe('partial')
  const transcript = page.getByRole('region', {
    name: 'Transcript',
    exact: true,
  })
  await transcript
    .getByRole('button', { name: /^Sửa đoạn / })
    .first()
    .click()
  const edited = 'E2E partial: transcript vẫn sửa được khi tóm tắt bị lỗi.'
  await page.getByRole('textbox', { name: 'Chỉnh sửa transcript' }).fill(edited)
  const saved = page.waitForResponse(
    (r) => r.request().method() === 'PATCH' && r.url().includes('/segments/'),
  )
  await page.getByRole('button', { name: 'Lưu thay đổi', exact: true }).click()
  expect((await saved).status()).toBe(200)
  await page.reload()
  await expect(transcript.getByText(edited, { exact: true })).toBeVisible()
})
