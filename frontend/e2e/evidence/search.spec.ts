import { execFileSync } from 'node:child_process'
import { writeFile } from 'node:fs/promises'
import { randomUUID } from 'node:crypto'
import { test, expect } from '../fixtures.js'
import { syntheticWav } from '../audio.js'

test('FE-04: real API search finds the oldest of eleven uploaded meetings', async ({
  page,
}, info) => {
  const ids: string[] = []
  const prefix = `FE04-${randomUUID()}`
  const title = `${prefix}-oldest`
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.name))
  try {
    for (let index = 0; index < 11; index++) {
      const audio = syntheticWav()
      const response = await page.request.post('/api/v1/meetings', {
        headers: { 'Idempotency-Key': randomUUID() },
        multipart: {
          title: index === 0 ? title : `${prefix}-newer-${index}`,
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
    const first = await page.request.get('/api/v1/meetings?page=1')
    const second = await page.request.get('/api/v1/meetings?page=2')
    expect(first.status()).toBe(200)
    expect(second.status()).toBe(200)
    const pageOne = await first.json()
    const pageTwo = await second.json()
    expect(
      pageOne.items.map((meeting: { id: string }) => meeting.id),
    ).not.toContain(ids[0])
    expect(
      pageTwo.items.map((meeting: { id: string }) => meeting.id),
    ).toContain(ids[0])
    await page.goto('/meetings')
    await expect(page.locator('.meeting-row')).toHaveCount(10)
    const result = page.waitForResponse((response) => {
      const url = new URL(response.url())
      return (
        response.request().method() === 'GET' &&
        url.pathname === '/api/v1/meetings' &&
        url.searchParams.get('q') === title
      )
    })
    await page
      .getByRole('textbox', { name: 'Tìm cuộc họp' })
      .fill(`  ${title}  `)
    const response = await result
    expect(response.status()).toBe(200)
    const data = await response.json()
    expect(data.total).toBe(1)
    expect(data.items.map((meeting: { id: string }) => meeting.id)).toEqual([
      ids[0],
    ])
    await expect(page.locator('.meeting-row')).toHaveCount(1)
    await expect(page.locator('.meeting-row')).toHaveAttribute(
      'href',
      `/meetings/${ids[0]}`,
    )
    await expect(page.getByText('Hiển thị 1 trên 1 cuộc họp')).toBeVisible()
    expect(errors).toEqual([])
    await writeFile(
      info.outputPath('search-result.json'),
      JSON.stringify(
        {
          source_commit: execFileSync('git', ['rev-parse', 'HEAD'], {
            encoding: 'utf8',
          }).trim(),
          scenario: 'eleven uploads; no worker',
          postgres_version: 16,
          synthetic_only: true,
          api_interception: false,
          retries: info.retry,
          total_uploaded: ids.length,
          oldest_id: ids[0],
          oldest_on_first_page: false,
          oldest_on_second_page: true,
          search_total: data.total,
          displayed_rows: 1,
          page_errors: errors,
          captured_at_utc: new Date().toISOString(),
        },
        null,
        2,
      ) + '\n',
      'utf8',
    )
  } finally {
    for (const id of ids) await page.request.delete(`/api/v1/meetings/${id}`)
  }
})
