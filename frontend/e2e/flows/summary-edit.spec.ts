import { writeFile } from 'node:fs/promises'
import { randomUUID } from 'node:crypto'
import { test, expect } from '@playwright/test'
import { syntheticWav } from '../audio.js'
import { createSyntheticUser } from '../backend-fixtures.js'
import { expectReady } from '../meeting.js'

test('FE-12/14/17: edited summary persists after reload with exactly one history event', async ({
  page,
}, info) => {
  const password = process.env.SEED_DEMO_PASSWORD!
  const owner = await createSyntheticUser(randomUUID())
  let meetingId: string | undefined
  const overview = 'Tổng quan E2E đã chỉnh sửa.'
  const point = 'Ý chính E2E được bổ sung.'
  const result = {
    beforeVersion: 0,
    afterVersion: 0,
    persisted: false,
    historyEvents: 0,
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
        title: 'E2E sửa tóm tắt',
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
    const originalResponse = await page.request.get(
      `/api/v1/meetings/${meetingId}/summary`,
    )
    expect(originalResponse.status()).toBe(200)
    const original = await originalResponse.json()
    expect(original.status).toBe('ready')
    expect(original.content.decisions.length).toBeGreaterThan(0)
    result.beforeVersion = original.version
    const expected = {
      overview,
      key_points: [
        ...original.content.key_points,
        { text: point, evidence_segment_ids: [] },
      ],
      decisions: original.content.decisions.slice(1),
    }
    await page.getByRole('button', { name: 'Chỉnh sửa', exact: true }).click()
    await page
      .getByRole('textbox', { name: 'Chỉnh sửa tổng quan', exact: true })
      .fill(overview)
    await page
      .getByRole('button', { name: 'Thêm ý chính', exact: true })
      .click()
    await page
      .getByRole('textbox', {
        name: `Ý chính ${expected.key_points.length}`,
        exact: true,
      })
      .fill(point)
    await page
      .getByRole('button', { name: 'Xóa decisions 1', exact: true })
      .click()
    const saved = page.waitForResponse(
      (response) =>
        response.request().method() === 'PUT' &&
        new URL(response.url()).pathname ===
          `/api/v1/meetings/${meetingId}/summary`,
    )
    await page.getByRole('button', { name: 'Lưu', exact: true }).click()
    const response = await saved
    expect(response.status()).toBe(200)
    expect(response.request().postDataJSON()).toEqual({
      content: expected,
      version: original.version,
    })
    await expect(page.getByText(overview, { exact: true })).toBeVisible()
    await page.reload()
    await expect(page.getByText(overview, { exact: true })).toBeVisible()
    await expect(
      page.locator('.note-section').filter({
        has: page.getByRole('heading', { name: 'Ý chính', exact: true }),
      }),
    ).toContainText(point)
    await expect(
      page.locator('.note-section').filter({
        has: page.getByRole('heading', { name: 'Quyết định', exact: true }),
      }),
    ).not.toContainText(original.content.decisions[0].text)
    const persistedResponse = await page.request.get(
      `/api/v1/meetings/${meetingId}/summary`,
    )
    expect(persistedResponse.status()).toBe(200)
    const persisted = await persistedResponse.json()
    expect(persisted.content).toEqual(expected)
    expect(persisted.version).toBe(original.version + 1)
    expect(persisted.is_edited).toBe(true)
    result.afterVersion = persisted.version
    result.persisted = true
    await page
      .locator('.notes-tabs')
      .getByRole('button', { name: 'Lịch sử', exact: true })
      .click()
    const history = page.getByRole('region', {
      name: 'Lịch sử chỉnh sửa',
      exact: true,
    })
    await expect(history.getByRole('listitem')).toHaveCount(1)
    await expect(history.getByRole('listitem')).toContainText('Tóm tắt')
    await expect(history.getByRole('listitem')).toContainText(overview)
    const editsResponse = await page.request.get(
      `/api/v1/meetings/${meetingId}/edits`,
    )
    expect(editsResponse.status()).toBe(200)
    const edits = await editsResponse.json()
    expect(edits.total).toBe(1)
    expect(edits.items).toHaveLength(1)
    expect(edits.items[0]).toMatchObject({
      entity_type: 'summary',
      action: 'update',
    })
    result.historyEvents = edits.total
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
        info.outputPath('summary-edit-result.json'),
        JSON.stringify(result, null, 2) + '\n',
        'utf8',
      )
    }
  }
})
