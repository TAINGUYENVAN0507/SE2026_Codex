import { expect, type Page } from '@playwright/test'
import { syntheticWav } from './audio.js'

export async function uploadMeeting(page: Page, title: string) {
  await page.goto('/meetings/new')
  await page
    .getByLabel('Chọn file audio', { exact: true })
    .setInputFiles(syntheticWav())
  await page.getByRole('textbox', { name: 'Tên cuộc họp' }).fill(title)
  await page.getByRole('checkbox').check()
  const created = page.waitForResponse(
    (r) =>
      r.url().endsWith('/api/v1/meetings') && r.request().method() === 'POST',
  )
  await page.getByRole('button', { name: 'Tạo biên bản', exact: true }).click()
  const response = await created
  expect(response.status(), await response.text()).toBe(201)
  const data = await response.json()
  await expect(page).toHaveURL(new RegExp(`/meetings/${data.meeting.id}$`))
  return data as { meeting: { id: string }; job: { id: string } }
}

export async function expectReady(page: Page) {
  await expect(
    page
      .getByRole('region', { name: 'Tiến độ xử lý cuộc họp' })
      .getByRole('status'),
  ).toHaveText('Hoàn tất xử lý', { timeout: 90_000 })
  const transcript = page.getByRole('region', {
    name: 'Transcript',
    exact: true,
  })
  await expect(
    transcript.getByRole('button', { name: /^Sửa đoạn / }).first(),
  ).toBeVisible()
  await expect(
    page.getByRole('region', { name: 'Player audio cuộc họp' }),
  ).toBeVisible()
}
