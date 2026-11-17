import { writeFile } from 'node:fs/promises'
import { randomUUID } from 'node:crypto'
import { test, expect } from '../fixtures.js'
import { syntheticWav } from '../audio.js'

test('FE-04: real API search treats % and _ as literal characters', async ({
  page,
}, info) => {
  const titles = ['Giảm 100% chi phí', 'Họp_nhóm', 'Họp nhóm']
  const ids: string[] = []
  const pageErrors: string[] = []
  const results: {
    q: string
    total: number
    ids: string[]
    displayed: number
  }[] = []
  page.on('pageerror', (error) => pageErrors.push(error.name))
  try {
    for (const title of titles) {
      const audio = syntheticWav()
      const response = await page.request.post('/api/v1/meetings', {
        headers: { 'Idempotency-Key': randomUUID() },
        multipart: {
          title,
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
      ids.push((await response.json()).meeting.id)
    }
    await page.goto('/meetings')
    for (const title of titles)
      await expect(page.getByText(title, { exact: true })).toBeVisible()
    for (const [q, expectedIndex] of [
      ['%', 0],
      ['_', 1],
      ['100%', 0],
    ] as const) {
      const result = page.waitForResponse((response) => {
        const url = new URL(response.url())
        return (
          response.request().method() === 'GET' &&
          url.pathname === '/api/v1/meetings' &&
          url.searchParams.get('q') === q
        )
      })
      await page.getByRole('textbox', { name: 'Tìm cuộc họp' }).fill(q)
      const response = await result
      expect(response.status()).toBe(200)
      const data = await response.json()
      expect.soft(data.total, `q=${q} chỉ khớp ký tự thật`).toBe(1)
      expect
        .soft(data.items.map((item: { id: string }) => item.id))
        .toEqual([ids[expectedIndex]])
      await expect
        .soft(page.locator('.meeting-row'))
        .toHaveCount(1, { timeout: 1500 })
      expect
        .soft(
          await page
            .locator('.meeting-row')
            .evaluateAll((rows) => rows.map((row) => row.getAttribute('href'))),
        )
        .toEqual([`/meetings/${ids[expectedIndex]}`])
      await expect
        .soft(page.getByText('Hiển thị 1 trên 1 cuộc họp'))
        .toBeVisible({ timeout: 1500 })
      results.push({
        q,
        total: data.total,
        ids: data.items.map((item: { id: string }) => item.id),
        displayed: await page.locator('.meeting-row').count(),
      })
    }
    expect(pageErrors).toEqual([])
    await writeFile(
      info.outputPath('wildcard-result.json'),
      JSON.stringify(
        {
          results,
          pageErrors,
          retries: info.retry,
          syntheticOnly: true,
          apiInterception: false,
        },
        null,
        2,
      ) + '\n',
      'utf8',
    )
  } finally {
    for (const id of ids) {
      const response = await page.request.delete(`/api/v1/meetings/${id}`)
      expect(response.status()).toBe(204)
    }
  }
})
