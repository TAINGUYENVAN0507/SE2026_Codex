import { test, expect } from '../fixtures.js'
import { uploadMeeting, expectReady } from '../meeting.js'
import { downloadExport } from '../exports.js'
import type { components } from '../../src/api/schema.js'
type SummaryData = components['schemas']['SummaryOut']
type TranscriptData = components['schemas']['TranscriptOut']

test('FE-18: tóm tắt thật, evidence tua đúng audio và tải đủ TXT/MD/JSON', async ({
  page,
}) => {
  // Pipeline fake tạo transcript 30 giây: audio tổng hợp phải đủ dài để kiểm seek.
  const { meeting } = await uploadMeeting(page, 'E2E tóm tắt và export', 30)
  await expectReady(page)
  const summaryResponse = await page.request.get(
    `/api/v1/meetings/${meeting.id}/summary`,
  )
  expect(summaryResponse.status()).toBe(200)
  const summary = (await summaryResponse.json()) as SummaryData
  expect(summary.status).toBe('ready')
  expect(summary.content).toBeTruthy()
  await expect(page.locator('.notes-panel')).toContainText(
    summary.content!.overview,
  )
  const transcript = (await (
    await page.request.get(`/api/v1/meetings/${meeting.id}/transcript`)
  ).json()) as TranscriptData
  const evidenceId = summary.content!.key_points?.flatMap(
    (p) => p.evidence_segment_ids ?? [],
  )[0]
  const segments = transcript.segments ?? []
  expect(segments.length).toBeGreaterThan(0)
  const segment = segments.find((s) => s.id === evidenceId)
  expect(
    segment,
    'Cần evidence thật, không để test qua mà bỏ kiểm seek',
  ).toBeTruthy()
  const audio = page.locator('.audio-region audio')
  await expect
    .poll(() => audio.evaluate((el: HTMLAudioElement) => el.duration))
    .toBeGreaterThan(29)
  const timestamp = new Date(Math.floor(segment!.start_sec) * 1000)
    .toISOString()
    .slice(11, 19)
  await page
    .locator('.notes-panel')
    .getByRole('button', {
      name: `Nghe bằng chứng từ ${timestamp}`,
      exact: true,
    })
    .first()
    .click()
  await expect
    .poll(() => audio.evaluate((el: HTMLAudioElement) => el.currentTime))
    .toBeCloseTo(segment!.start_sec, 1)
  for (const format of ['txt', 'md', 'json'] as const) {
    const content = await downloadExport(page, format)
    if (format === 'json') {
      const data = JSON.parse(content)
      expect(data.schema_version).toBe('1.1')
      expect(data.meeting.id).toBe(meeting.id)
      expect(data.summary.overview).toBe(summary.content!.overview)
      expect(data.segments.length).toBe(segments.length)
    } else {
      expect(content).toContain(summary.content!.overview)
      expect(content).toContain(timestamp)
      expect(content).toContain('Bằng chứng:')
    }
  }
})
