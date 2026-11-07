import { test, expect } from '../fixtures.js'
import { uploadMeeting, expectReady } from '../meeting.js'
import { downloadExport } from '../exports.js'
import type { Locator } from '@playwright/test'
import type { components } from '../../src/api/schema.js'

type Summary = components['schemas']['SummaryOut']
type Transcript = components['schemas']['TranscriptOut']
type Actions = components['schemas']['ActionItemListOut']

test('FE-18: từng ý/công việc có cùng evidence hoặc nhãn thiếu trong UI và TXT/MD', async ({
  page,
}) => {
  const { meeting } = await uploadMeeting(
    page,
    'E2E đối chiếu từng dẫn chứng',
    30,
  )
  await expectReady(page)
  const summaryUrl = `/api/v1/meetings/${meeting.id}/summary`
  const original = (await (
    await page.request.get(summaryUrl)
  ).json()) as Summary
  const missingPoint = 'Ý kiểm tra E2E chưa có dẫn chứng'
  const missingTask = 'Công việc E2E chưa có dẫn chứng'
  const notes = page.locator('.notes-panel')
  await notes.getByRole('button', { name: 'Chỉnh sửa', exact: true }).click()
  await notes.getByRole('button', { name: 'Thêm ý chính', exact: true }).click()
  await notes
    .getByRole('textbox', {
      name: `Ý chính ${(original.content!.key_points ?? []).length + 1}`,
      exact: true,
    })
    .fill(missingPoint)
  const saved = page.waitForResponse(
    (r) => r.url().endsWith(summaryUrl) && r.request().method() === 'PUT',
  )
  await notes.getByRole('button', { name: 'Lưu', exact: true }).click()
  expect((await saved).status()).toBe(200)
  await notes
    .locator('.notes-tabs')
    .getByRole('button', { name: 'Công việc', exact: true })
    .click()
  await notes
    .getByRole('textbox', { name: 'Thêm nội dung', exact: true })
    .fill(missingTask)
  const created = page.waitForResponse(
    (r) => r.url().endsWith('/action-items') && r.request().method() === 'POST',
  )
  await notes
    .getByRole('button', { name: 'Thêm công việc', exact: true })
    .click()
  expect((await created).status()).toBe(201)
  await page.reload()
  await expectReady(page)
  const documents = [
    await downloadExport(page, 'txt'),
    await downloadExport(page, 'md'),
  ]
  const transcript = (await (
    await page.request.get(`/api/v1/meetings/${meeting.id}/transcript`)
  ).json()) as Transcript
  let verified = 0
  let unverified = 0
  async function checkClaim(row: Locator, text: string, ids: string[] = []) {
    await expect(row).toHaveCount(1)
    await expect(row).toBeVisible()
    const references = [...new Set(ids)].map((id) => {
      const segment = (transcript.segments ?? []).find((s) => s.id === id)
      expect(
        segment,
        `Evidence ${id} phải trỏ tới segment tồn tại`,
      ).toBeTruthy()
      return new Date(Math.floor(segment!.start_sec) * 1000)
        .toISOString()
        .slice(11, 19)
    })
    const shown = (await row.locator('.evidence').allTextContents()).map((t) =>
      t.trim(),
    )
    expect(shown).toEqual(references)
    for (const document of documents) {
      const line = document.split('\n').find((l) => l.includes(text))
      expect(line, `File phải chứa chính ý/công việc: ${text}`).toBeTruthy()
      const evidence = line!.match(/\(Bằng chứng: ([^)]+)\)/)?.[1] ?? ''
      expect(evidence.match(/\d{2}:\d{2}:\d{2}/g) ?? []).toEqual(shown)
      if (!ids.length) expect(line).toContain('Chưa có bằng chứng')
    }
    if (ids.length) {
      verified++
      await expect(row.locator('.unverified-evidence')).toHaveCount(0)
    } else {
      unverified++
      await expect(row.locator('.unverified-evidence')).toHaveText(
        'Chưa có bằng chứng',
      )
    }
  }
  const summary = (await (await page.request.get(summaryUrl)).json()) as Summary
  const points = [
    ...(summary.content!.key_points ?? []),
    ...(summary.content!.decisions ?? []),
  ]
  expect(points.some((p) => p.text === missingPoint)).toBe(true)
  for (const point of points)
    await checkClaim(
      notes.locator('.decision').filter({ hasText: point.text }),
      point.text,
      point.evidence_segment_ids,
    )
  await notes
    .locator('.notes-tabs')
    .getByRole('button', { name: 'Công việc', exact: true })
    .click()
  const actions = (await (
    await page.request.get(`/api/v1/meetings/${meeting.id}/action-items`)
  ).json()) as Actions
  const items = actions.items ?? []
  expect(items.some((item) => item.description === missingTask)).toBe(true)
  for (const item of items)
    await checkClaim(
      notes.locator('.task').filter({ hasText: item.description }),
      item.description,
      item.evidence_segment_ids,
    )
  expect(verified).toBeGreaterThan(0)
  expect(unverified).toBe(2)
})
