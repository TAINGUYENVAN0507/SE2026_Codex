import { writeFile, readdir, realpath, unlink } from 'node:fs/promises'
import path from 'node:path'
import { randomUUID } from 'node:crypto'
import { test, expect } from '@playwright/test'
import { syntheticWav } from '../audio.js'
import { createSyntheticUser } from '../backend-fixtures.js'
import { expectReady } from '../meeting.js'
import type { components } from '../../src/api/schema.js'

test('FE-19/17: missing audio returns 404 and the UI keeps the transcript without saying expired', async ({
  page,
}, info) => {
  if (process.env.E2E_MANUAL_WORKER)
    throw new Error('Không đặt E2E_MANUAL_WORKER; cần worker chạy.')
  const storage = process.env.E2E_STORAGE_DIR
  if (!storage) throw new Error('Thiếu storage riêng của stack E2E.')
  const password = process.env.SEED_DEMO_PASSWORD!
  const owner = await createSyntheticUser(randomUUID())
  let meetingId: string | undefined
  const result = {
    removedFiles: 0,
    apiStatus: 0,
    errorCode: '',
    metadataUnavailable: false,
    retentionFuture: false,
    transcriptPreserved: false,
    missingNotice: false,
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
    const audio = syntheticWav()
    const created = await page.request.post('/api/v1/meetings', {
      headers: { 'Idempotency-Key': randomUUID() },
      multipart: {
        title: 'E2E audio mất file',
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
    const base = `/api/v1/meetings/${meetingId}`
    await page.goto(`/meetings/${meetingId}`)
    await expectReady(page)
    const beforeResponse = await page.request.get(`${base}/transcript`)
    expect(beforeResponse.status()).toBe(200)
    const before =
      (await beforeResponse.json()) as components['schemas']['TranscriptOut']
    expect(before.segments?.length).toBeGreaterThan(0)
    expect((await page.request.get(`${base}/audio`)).status()).toBe(200)
    const root = await realpath(storage)
    const directory = await realpath(path.join(root, 'audio', meetingId!))
    if (
      path.dirname(directory) !== path.join(root, 'audio') ||
      path.basename(directory) !== meetingId
    )
      throw new Error('Không xóa file ngoài storage của cuộc họp E2E riêng.')
    const files = (await readdir(directory, { withFileTypes: true })).filter(
      (entry) => entry.isFile() && /^original\.[a-z0-9]+$/i.test(entry.name),
    )
    expect(files).toHaveLength(1)
    for (const entry of files) {
      const target = await realpath(path.join(directory, entry.name))
      if (path.dirname(target) !== directory)
        throw new Error('File audio trỏ ra ngoài thư mục E2E.')
      await unlink(target)
      result.removedFiles++
    }
    const missing = await page.request.get(`${base}/audio`)
    result.apiStatus = missing.status()
    expect(result.apiStatus).toBe(404)
    result.errorCode = (await missing.json()).error.code
    expect(['NOT_FOUND', 'AUDIO_NOT_FOUND']).toContain(result.errorCode)
    const metadataResponse = await page.request.get(base)
    expect(metadataResponse.status()).toBe(200)
    const metadata =
      (await metadataResponse.json()) as components['schemas']['MeetingDetailOut']
    expect(metadata.audio.available).toBe(false)
    result.metadataUnavailable = true
    expect(Date.parse(metadata.audio.retention_until!)).toBeGreaterThan(
      Date.now(),
    )
    result.retentionFuture = true
    await page.reload()
    const player = page.getByRole('region', {
      name: 'Player audio cuộc họp',
      exact: true,
    })
    await expect(player.getByRole('status')).toHaveText(
      'Không tìm thấy file audio',
    )
    await expect(
      page.getByText('Audio đã hết hạn lưu trữ', { exact: true }),
    ).toHaveCount(0)
    await expect(player.locator('audio')).toHaveCount(0)
    await expect(
      page
        .getByRole('region', { name: 'Transcript', exact: true })
        .getByText(before.segments![0].text, { exact: true }),
    ).toBeVisible()
    const afterResponse = await page.request.get(`${base}/transcript`)
    expect(afterResponse.status()).toBe(200)
    expect(await afterResponse.json()).toEqual(before)
    result.transcriptPreserved = true
    result.missingNotice = true
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
        info.outputPath('missing-audio-result.json'),
        JSON.stringify(result, null, 2) + '\n',
        'utf8',
      )
    }
  }
})
