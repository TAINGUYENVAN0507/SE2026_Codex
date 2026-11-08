import { test, expect } from '../fixtures.js'
import { uploadMeeting, expectReady } from '../meeting.js'
import { expireSyntheticAudio } from '../backend-fixtures.js'
import type { components } from '../../src/api/schema.js'

test('FE-19: cleanup xóa audio/artifacts hết hạn thật, transcript vẫn đọc được', async ({
  page,
}) => {
  const { meeting } = await uploadMeeting(page, 'E2E audio hết hạn', 30)
  await expectReady(page)
  const base = `/api/v1/meetings/${meeting.id}`
  const before = (await (
    await page.request.get(`${base}/transcript`)
  ).json()) as components['schemas']['TranscriptOut']
  expect((await page.request.get(`${base}/audio`)).status()).toBe(200)
  const cleanup = await expireSyntheticAudio(meeting.id)
  expect(cleanup.audio_removed).toBe(true)
  expect(cleanup.transcript_preserved).toBe(true)
  expect(cleanup.segments).toBeGreaterThan(0)
  expect((await page.request.get(`${base}/audio`)).status()).toBe(410)
  const metadata = await (await page.request.get(base)).json()
  expect(metadata.audio.available).toBe(false)
  await page.reload()
  await expect(
    page.getByText('Audio đã hết hạn lưu trữ', { exact: true }),
  ).toBeVisible()
  await expect(
    page
      .getByRole('region', { name: 'Transcript', exact: true })
      .getByText(before.segments![0].text, { exact: true }),
  ).toBeVisible()
  expect(await (await page.request.get(`${base}/transcript`)).json()).toEqual(
    before,
  )
  await expect(page.locator('.audio-region audio')).toHaveCount(0)
})
