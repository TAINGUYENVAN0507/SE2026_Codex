import { test, expect } from '../fixtures.js'
import { uploadMeeting, expectReady } from '../meeting.js'

test('FE-17: chỉnh sửa tồn tại sau reload và có đúng event trong lịch sử', async ({
  page,
}) => {
  const { meeting } = await uploadMeeting(page, 'E2E chỉnh sửa và lịch sử')
  await expectReady(page)
  const original = await (
    await page.request.get(`/api/v1/meetings/${meeting.id}/transcript`)
  ).json()
  const segment = original.segments[0]
  const speaker = original.speakers[0]
  const editedText = 'Nội dung tổng hợp E2E đã chỉnh sửa.'
  const renamed = 'Người nói E2E'
  await page
    .getByRole('button', { name: `Sửa đoạn ${segment.id}`, exact: true })
    .click()
  await page
    .getByRole('textbox', { name: 'Chỉnh sửa transcript' })
    .fill(editedText)
  const patched = page.waitForResponse(
    (r) =>
      r.request().method() === 'PATCH' &&
      r.url().endsWith(`/segments/${segment.id}`),
  )
  await page.getByRole('button', { name: 'Lưu thay đổi', exact: true }).click()
  expect((await patched).status()).toBe(200)
  await page
    .getByRole('button', {
      name: `Đổi tên ${speaker.display_name}`,
      exact: true,
    })
    .click()
  await page
    .getByRole('textbox', { name: `Tên mới của ${speaker.display_name}` })
    .fill(renamed)
  const renamedResponse = page.waitForResponse(
    (r) =>
      r.request().method() === 'PATCH' &&
      r.url().endsWith(`/speakers/${speaker.id}`),
  )
  await page.getByRole('button', { name: 'Lưu', exact: true }).click()
  expect((await renamedResponse).status()).toBe(200)
  await page
    .locator('.notes-tabs')
    .getByRole('button', { name: 'Công việc' })
    .click()
  await page
    .getByRole('textbox', { name: 'Thêm nội dung' })
    .fill('Công việc E2E mới')
  const created = page.waitForResponse(
    (r) => r.request().method() === 'POST' && r.url().endsWith('/action-items'),
  )
  await page
    .getByRole('button', { name: 'Thêm công việc', exact: true })
    .click()
  const createdResponse = await created
  expect(createdResponse.status()).toBe(201)
  const item = await createdResponse.json()
  await page.getByRole('button', { name: `Sửa công việc ${item.id}` }).click()
  await page
    .getByRole('textbox', { name: 'Sửa nội dung' })
    .fill('Công việc E2E đã sửa')
  const updated = page.waitForResponse(
    (r) =>
      r.request().method() === 'PATCH' &&
      r.url().endsWith(`/action-items/${item.id}`),
  )
  await page.getByRole('button', { name: 'Lưu công việc', exact: true }).click()
  expect((await updated).status()).toBe(200)
  await page.reload()
  await expect(page.getByText(editedText, { exact: true })).toBeVisible()
  await expect(
    page.getByRole('button', { name: renamed, exact: true }),
  ).toBeVisible()
  await page
    .locator('.notes-tabs')
    .getByRole('button', { name: 'Công việc' })
    .click()
  await expect(
    page.getByText('Công việc E2E đã sửa', { exact: true }),
  ).toBeVisible()
  page.once('dialog', (dialog) => dialog.accept())
  const removed = page.waitForResponse(
    (r) =>
      r.request().method() === 'DELETE' &&
      r.url().includes(`/action-items/${item.id}`),
  )
  await page.getByRole('button', { name: `Xóa công việc ${item.id}` }).click()
  expect((await removed).status()).toBe(204)
  await page.reload()
  await page
    .locator('.notes-tabs')
    .getByRole('button', { name: 'Công việc' })
    .click()
  await expect(
    page.getByRole('button', { name: 'Thêm công việc', exact: true }),
  ).toBeVisible()
  await expect(
    page.getByText('Công việc E2E đã sửa', { exact: true }),
  ).toHaveCount(0)
  await page
    .locator('.notes-tabs')
    .getByRole('button', { name: 'Lịch sử' })
    .click()
  const history = page.getByRole('region', { name: 'Lịch sử chỉnh sửa' })
  await expect(history.getByRole('listitem')).toHaveCount(5)
  await expect(history).toContainText(editedText)
  await expect(history).toContainText(renamed)
  const events = await (
    await page.request.get(`/api/v1/meetings/${meeting.id}/edits`)
  ).json()
  expect(events.total).toBe(5)
  expect(
    events.items
      .filter(
        (event: { entity_type: string }) => event.entity_type === 'action_item',
      )
      .map((event: { action: string }) => event.action)
      .sort(),
  ).toEqual(['create', 'delete', 'update'])
})
