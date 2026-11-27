import { writeFile } from 'node:fs/promises'
import { randomUUID } from 'node:crypto'
import { test, expect } from '@playwright/test'
import { syntheticWav } from '../audio.js'
import { createSyntheticUser } from '../backend-fixtures.js'
import { expectReady } from '../meeting.js'
import type { components } from '../../src/api/schema.js'

type SummaryData = components['schemas']['SummaryOut']
type TranscriptData = components['schemas']['TranscriptOut']

test('FE-18/17: a summary evidence click seeks real server audio into the cited segment', async ({
  page,
}, info) => {
  if (process.env.E2E_MANUAL_WORKER)
    throw new Error(
      'Không đặt E2E_MANUAL_WORKER; bài kiểm này cần worker chạy.',
    )
  const password = process.env.SEED_DEMO_PASSWORD!
  const owner = await createSyntheticUser(randomUUID())
  let meetingId: string | undefined
  const result = {
    segmentStart: 0,
    segmentEnd: 0,
    audioDuration: 0,
    before: 0,
    after: 0,
    cleanedMeeting: false,
    cleanedUser: false,
    retries: info.retry,
    syntheticOnly: true,
    apiInterception: false,
    pageErrors: [] as string[],
  }
  page.on('pageerror', (error) => result.pageErrors.push(error.name))
  try {
    expect(
      (
        await page.request.post('/api/v1/auth/login', {
          data: { email: owner.email, password },
        })
      ).status(),
    ).toBe(200)
    const audio = syntheticWav(60)
    const created = await page.request.post('/api/v1/meetings', {
      headers: { 'Idempotency-Key': randomUUID() },
      multipart: {
        title: 'E2E bấm dẫn chứng',
        consent_confirmed: 'true',
        source: 'upload',
        file: {
          name: audio.name,
          mimeType: audio.mimeType,
          buffer: audio.buffer,
        },
      },
    })
    expect(created.status()).toBe(201)
    meetingId = (await created.json()).meeting.id
    await page.goto(`/meetings/${meetingId}`)
    await expectReady(page)
    await expect(
      page.getByRole('button', { name: 'Chỉnh sửa', exact: true }),
    ).toBeVisible()
    const summaryResponse = await page.request.get(
      `/api/v1/meetings/${meetingId}/summary`,
    )
    const transcriptResponse = await page.request.get(
      `/api/v1/meetings/${meetingId}/transcript`,
    )
    expect(summaryResponse.status()).toBe(200)
    expect(transcriptResponse.status()).toBe(200)
    const summary = (await summaryResponse.json()) as SummaryData
    const transcript = (await transcriptResponse.json()) as TranscriptData
    expect(summary.status).toBe('ready')
    const candidates = (summary.content?.key_points ?? []).flatMap(
      (point, pointIndex) =>
        (point.evidence_segment_ids ?? []).flatMap((id) => {
          const segment = transcript.segments?.find((item) => item.id === id)
          return segment ? [{ segment, pointIndex }] : []
        }),
    )
    const target = candidates.find(
      ({ segment }) => segment.start_sec > 0 && segment.end_sec < 60,
    )
    // Mốc khác 0 để test phải đỏ nếu nút không gọi player.seek.
    expect(target).toBeDefined()
    if (!target)
      throw new Error(
        'Cần một ý chính trỏ tới segment khác mốc 0 trong WAV tổng hợp.',
      )
    const { segment, pointIndex } = target
    result.segmentStart = segment.start_sec
    result.segmentEnd = segment.end_sec
    const media = page
      .getByRole('region', { name: 'Player audio cuộc họp', exact: true })
      .locator('audio')
    await expect(media).toHaveAttribute(
      'src',
      `/api/v1/meetings/${meetingId}/audio`,
    )
    await expect
      .poll(() =>
        media.evaluate((element: HTMLAudioElement) => element.duration),
      )
      .toBeGreaterThan(segment.end_sec)
    result.audioDuration = await media.evaluate(
      (element: HTMLAudioElement) => element.duration,
    )
    result.before = await media.evaluate(
      (element: HTMLAudioElement) => element.currentTime,
    )
    expect(result.before).toBe(0)
    const stamp = new Date(Math.floor(segment.start_sec) * 1000)
      .toISOString()
      .slice(11, 19)
    const row = page
      .locator('.note-section')
      .filter({
        has: page.getByRole('heading', { name: 'Ý chính', exact: true }),
      })
      .locator('.decision')
      .nth(pointIndex)
    await row
      .getByRole('button', { name: `Nghe bằng chứng từ ${stamp}`, exact: true })
      .click()
    await expect
      .poll(() =>
        media.evaluate((element: HTMLAudioElement) => element.currentTime),
      )
      .toBeGreaterThanOrEqual(segment.start_sec)
    await expect
      .poll(() =>
        media.evaluate((element: HTMLAudioElement) => element.seeking),
      )
      .toBe(false)
    result.after = await media.evaluate(
      (element: HTMLAudioElement) => element.currentTime,
    )
    expect(result.after).toBeGreaterThanOrEqual(segment.start_sec)
    expect(result.after).toBeLessThanOrEqual(segment.end_sec)
    expect(
      await media.evaluate((element: HTMLAudioElement) => element.paused),
    ).toBe(true)
    expect(result.pageErrors).toEqual([])
  } finally {
    try {
      expect(
        (
          await page.request.post('/api/v1/auth/login', {
            data: { email: owner.email, password },
          })
        ).status(),
      ).toBe(200)
      if (meetingId) {
        expect(
          (await page.request.delete(`/api/v1/meetings/${meetingId}`)).status(),
        ).toBe(204)
        result.cleanedMeeting = true
      }
      expect(
        (await (await page.request.get('/api/v1/meetings')).json()).total,
      ).toBe(0)
    } finally {
      expect((await page.request.delete('/api/v1/auth/me')).status()).toBe(204)
      result.cleanedUser = true
      await writeFile(
        info.outputPath('evidence-seek-result.json'),
        JSON.stringify(result, null, 2) + '\n',
        'utf8',
      )
    }
  }
})
