import { writeFile } from 'node:fs/promises'
import { randomUUID } from 'node:crypto'
import { test, expect } from '@playwright/test'
import { syntheticWav } from '../audio.js'
import { createSyntheticUser } from '../backend-fixtures.js'

test('FE-04: real API returns from a deleted empty page and explains an empty status filter', async ({
  page,
}, info) => {
  if (process.env.E2E_MANUAL_WORKER !== '1')
    throw new Error(
      'Kịch bản này phải giữ worker dừng để các cuộc họp còn queued.',
    )
  const password = process.env.SEED_DEMO_PASSWORD!
  const owner = await createSyntheticUser(randomUUID())
  const remaining = new Set<string>()
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.name))
  const result = {
    created: 0,
    queued: 0,
    page2Items: 0,
    emptyPageTotal: 0,
    returnedPage: 0,
    visibleRows: 0,
    statusEmpty: false,
    cleanedMeetings: 0,
    cleanedUser: false,
    retries: info.retry,
    syntheticOnly: true,
    apiInterception: false,
    pageErrors,
  }
  try {
    expect(
      (
        await page.request.post('/api/v1/auth/login', {
          data: { email: owner.email, password },
        })
      ).status(),
    ).toBe(200)
    // FE-04: user riêng không có cuộc họp seed; tạo đúng 11 mục qua API.
    expect(
      (await (await page.request.get('/api/v1/meetings')).json()).total,
    ).toBe(0)
    for (let index = 1; index <= 11; index++) {
      const audio = syntheticWav()
      const response = await page.request.post('/api/v1/meetings', {
        headers: { 'Idempotency-Key': randomUUID() },
        multipart: {
          title: `E2E trang rỗng ${index}`,
          consent_confirmed: 'true',
          source: 'upload',
          file: {
            name: audio.name,
            mimeType: audio.mimeType,
            buffer: audio.buffer,
          },
        },
      })
      expect(response.status()).toBe(201)
      const { meeting } = await response.json()
      remaining.add(meeting.id)
      result.created++
      expect(meeting.status).toBe('queued')
      result.queued++
    }
    await page.goto('/meetings')
    await expect(page.locator('.meeting-row')).toHaveCount(10)
    await expect(page.getByText('Hiển thị 10 trên 11 cuộc họp')).toBeVisible()
    const secondPage = page.waitForResponse((response) => {
      const url = new URL(response.url())
      return (
        response.request().method() === 'GET' &&
        url.pathname === '/api/v1/meetings' &&
        url.searchParams.get('page') === '2'
      )
    })
    await page.getByRole('button', { name: 'Trang sau' }).click()
    const page2Response = await secondPage
    expect(page2Response.status()).toBe(200)
    const page2 = await page2Response.json()
    expect(page2.total).toBe(11)
    expect(page2.page).toBe(2)
    expect(page2.items).toHaveLength(1)
    expect(page2.items[0].status).toBe('queued')
    result.page2Items = page2.items.length
    const deletedId: string = page2.items[0].id
    expect(remaining.has(deletedId)).toBe(true)
    await expect(page.locator('.meeting-row')).toHaveCount(1)
    await expect(
      page.locator(`.meeting-row[href="/meetings/${deletedId}"]`),
    ).toBeVisible()
    await expect(page.getByText('Trang 2', { exact: true })).toBeVisible()
    const emptyPoll = page.waitForResponse(async (response) => {
      const url = new URL(response.url())
      if (
        response.request().method() !== 'GET' ||
        url.pathname !== '/api/v1/meetings' ||
        url.searchParams.get('page') !== '2' ||
        response.status() !== 200
      )
        return false
      const data = await response.json()
      return data.total === 10 && data.items.length === 0
    })
    const firstPage = page.waitForResponse(async (response) => {
      const url = new URL(response.url())
      if (
        response.request().method() !== 'GET' ||
        url.pathname !== '/api/v1/meetings' ||
        url.searchParams.get('page') !== '1' ||
        response.status() !== 200
      )
        return false
      const data = await response.json()
      return data.page === 1 && data.total === 10 && data.items.length === 10
    })
    expect(
      (await page.request.delete(`/api/v1/meetings/${deletedId}`)).status(),
    ).toBe(204)
    remaining.delete(deletedId)
    result.cleanedMeetings++
    result.emptyPageTotal = (await (await emptyPoll).json()).total
    result.returnedPage = (await (await firstPage).json()).page
    await expect(page.getByText('Hiển thị 10 trên 10 cuộc họp')).toBeVisible()
    await expect(page.locator('.meeting-row')).toHaveCount(10)
    await expect(
      page.getByRole('heading', { name: 'Chưa có cuộc họp' }),
    ).toHaveCount(0)
    await expect(page.locator('.empty-state')).toHaveCount(0)
    await expect(
      page.getByRole('navigation', { name: 'Phân trang cuộc họp' }),
    ).toHaveCount(0)
    result.visibleRows = await page.locator('.meeting-row').count()
    await page.getByRole('button', { name: /Có lỗi/ }).click()
    await expect(
      page.getByRole('heading', { name: 'Không có cuộc họp ở trạng thái này' }),
    ).toBeVisible()
    await expect(
      page.getByRole('heading', { name: 'Chưa có cuộc họp' }),
    ).toHaveCount(0)
    await expect(page.getByText('Hiển thị 0 trên 0 cuộc họp')).toBeVisible()
    result.statusEmpty = true
    expect(pageErrors).toEqual([])
  } finally {
    // Chỉ dọn user/mục tổng hợp của test, kể cả khi assertion phía trên thất bại.
    try {
      const signedIn = await page.request.post('/api/v1/auth/login', {
        data: { email: owner.email, password },
      })
      expect(signedIn.status()).toBe(200)
      for (const id of remaining) {
        expect(
          (await page.request.delete(`/api/v1/meetings/${id}`)).status(),
        ).toBe(204)
        result.cleanedMeetings++
      }
      expect(
        (await (await page.request.get('/api/v1/meetings')).json()).total,
      ).toBe(0)
    } finally {
      expect((await page.request.delete('/api/v1/auth/me')).status()).toBe(204)
      result.cleanedUser = true
      await writeFile(
        info.outputPath('empty-page-result.json'),
        JSON.stringify(result, null, 2) + '\n',
        'utf8',
      )
    }
  }
})
