import { randomUUID } from 'node:crypto'
import { test, expect } from '@playwright/test'
import { createSyntheticUser } from '../backend-fixtures.js'
import { uploadMeeting, expectReady } from '../meeting.js'
import { syntheticWav } from '../audio.js'

test('FE-19: xóa tài khoản thật, mất phiên, không đăng nhập lại và không ảnh hưởng user khác', async ({
  page,
  playwright,
  baseURL,
}) => {
  test.setTimeout(180_000)
  const password = process.env.SEED_DEMO_PASSWORD!
  const owner = await createSyntheticUser(randomUUID())
  const other = await createSyntheticUser(randomUUID())
  const control = await playwright.request.newContext({ baseURL })
  async function signIn(email: string) {
    await page.goto('/login')
    await page.getByLabel('Email', { exact: true }).fill(email)
    await page.getByLabel('Mật khẩu', { exact: true }).fill(password)
    await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
    await expect(page).toHaveURL(/\/meetings$/)
  }
  try {
    await signIn(owner.email)
    for (let i = 0; i < 2; i++) {
      await uploadMeeting(page, `E2E account erasure ${i}`, 30)
      await expectReady(page)
    }
    expect(
      (
        await control.post('/api/v1/auth/login', {
          data: { email: other.email, password },
        })
      ).status(),
    ).toBe(200)
    const wav = syntheticWav(30)
    const created = await control.post('/api/v1/meetings', {
      headers: { 'Idempotency-Key': randomUUID() },
      multipart: {
        file: { name: wav.name, mimeType: wav.mimeType, buffer: wav.buffer },
        title: 'E2E other account preserved',
        consent_confirmed: 'true',
        source: 'upload',
      },
    })
    expect(created.status()).toBe(201)
    const { meeting } = await created.json()
    await expect
      .poll(
        async () =>
          (await (await control.get(`/api/v1/meetings/${meeting.id}`)).json())
            .status,
        { timeout: 90_000 },
      )
      .toBe('ready')
    const previousSession = await playwright.request.newContext({
      baseURL,
      storageState: await page.context().storageState(),
    })
    try {
      await page.goto('/settings')
      await page
        .getByRole('button', { name: 'Xóa tài khoản', exact: true })
        .click()
      await page
        .getByRole('textbox', { name: /Gõ lại email/ })
        .fill(owner.email)
      const removed = page.waitForResponse(
        (r) =>
          new URL(r.url()).pathname === '/api/v1/auth/me' &&
          r.request().method() === 'DELETE',
      )
      await page
        .getByRole('button', { name: 'Xóa tài khoản vĩnh viễn', exact: true })
        .click()
      expect((await removed).status()).toBe(204)
      await expect(page).toHaveURL(/\/login$/)
      expect(
        (await page.context().cookies()).some(
          (c) => c.name === 'session_token',
        ),
      ).toBe(false)
      expect((await previousSession.get('/api/v1/auth/me')).status()).toBe(401)
      await page.getByLabel('Email', { exact: true }).fill(owner.email)
      await page.getByLabel('Mật khẩu', { exact: true }).fill(password)
      const denied = page.waitForResponse(
        (r) =>
          new URL(r.url()).pathname === '/api/v1/auth/login' &&
          r.request().method() === 'POST',
      )
      await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
      expect((await denied).status()).toBe(401)
      await expect(page.getByRole('alert')).toContainText(
        'Email hoặc mật khẩu không chính xác',
      )
      await page.goto('/meetings')
      await expect(page).toHaveURL(/\/login/)
      expect(
        (await control.get(`/api/v1/meetings/${meeting.id}`)).status(),
      ).toBe(200)
      expect((await control.get('/api/v1/auth/me')).status()).toBe(200)
      expect(
        (
          await control.post('/api/v1/auth/login', {
            data: { email: other.email, password },
          })
        ).status(),
      ).toBe(200)
    } finally {
      await previousSession.dispose()
    }
  } finally {
    // Chỉ xóa các user tổng hợp do chính test tạo; user demo chung không bị tác động.
    for (const user of [owner, other]) {
      const session = await playwright.request.newContext({ baseURL })
      try {
        const result = await session.post('/api/v1/auth/login', {
          data: { email: user.email, password },
        })
        if (result.status() === 200)
          expect((await session.delete('/api/v1/auth/me')).status()).toBe(204)
        else expect(result.status()).toBe(401)
      } finally {
        await session.dispose()
      }
    }
    await control.dispose()
  }
})
