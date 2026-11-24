import { writeFile } from 'node:fs/promises'
import { randomUUID } from 'node:crypto'
import { test, expect } from '@playwright/test'
import { syntheticWav } from '../audio.js'
import { createSyntheticUser } from '../backend-fixtures.js'

test('FE-17: real API keeps a renamed meeting after reload and finds it by search', async ({
  page,
}, info) => {
  if (process.env.E2E_MANUAL_WORKER !== '1')
    throw new Error('Cần dừng worker trong kịch bản đổi tên.')
  const password = process.env.SEED_DEMO_PASSWORD!
  const owner = await createSyntheticUser(randomUUID())
  const title = 'Họp_đổi tên 100%'
  let meetingId: string | undefined
  const result = {
    beforeVersion: 0,
    afterVersion: 0,
    reloadedTitle: false,
    apiTitle: false,
    searchTotal: 0,
    searchCorrectId: false,
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
        title: 'E2E tên ban đầu',
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
    const { meeting } = await created.json()
    meetingId = meeting.id
    expect(meeting.status).toBe('queued')
    const before = await page.request.get(`/api/v1/meetings/${meetingId}`)
    expect(before.status()).toBe(200)
    result.beforeVersion = (await before.json()).version
    await page.goto(`/meetings/${meetingId}`)
    await page.getByRole('button', { name: 'Đổi tên cuộc họp' }).click()
    await page.getByRole('textbox', { name: 'Tên cuộc họp' }).fill(title)
    const saved = page.waitForResponse(
      (response) =>
        response.request().method() === 'PATCH' &&
        new URL(response.url()).pathname === `/api/v1/meetings/${meetingId}`,
    )
    await page.getByRole('button', { name: 'Lưu tên cuộc họp' }).click()
    const response = await saved
    expect(response.status()).toBe(200)
    expect(response.request().postDataJSON()).toEqual({
      title,
      version: result.beforeVersion,
    })
    await expect(
      page.getByRole('heading', { name: title, exact: true }),
    ).toBeVisible()
    await page.reload()
    await expect(
      page.getByRole('heading', { name: title, exact: true }),
    ).toBeVisible()
    result.reloadedTitle = true
    const after = await page.request.get(`/api/v1/meetings/${meetingId}`)
    expect(after.status()).toBe(200)
    const persisted = await after.json()
    expect(persisted.title).toBe(title)
    expect(persisted.version).toBe(result.beforeVersion + 1)
    result.apiTitle = true
    result.afterVersion = persisted.version
    await page.goto('/meetings')
    const searched = page.waitForResponse((response) => {
      const url = new URL(response.url())
      return (
        response.request().method() === 'GET' &&
        url.pathname === '/api/v1/meetings' &&
        url.searchParams.get('q') === '100%'
      )
    })
    await page.getByRole('textbox', { name: 'Tìm cuộc họp' }).fill('100%')
    const search = await searched
    expect(search.status()).toBe(200)
    const data = await search.json()
    expect(data.total).toBe(1)
    expect(data.items.map((item: { id: string }) => item.id)).toEqual([
      meetingId,
    ])
    await expect(page.locator('.meeting-row')).toHaveCount(1)
    await expect(
      page.locator(`.meeting-row[href="/meetings/${meetingId}"]`),
    ).toContainText(title)
    await expect(page.getByText('Hiển thị 1 trên 1 cuộc họp')).toBeVisible()
    result.searchTotal = data.total
    result.searchCorrectId = data.items[0].id === meetingId
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
        info.outputPath('rename-result.json'),
        JSON.stringify(result, null, 2) + '\n',
        'utf8',
      )
    }
  }
})
