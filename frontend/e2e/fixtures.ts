import { test as base, expect, type Page } from '@playwright/test'

export async function login(page: Page) {
  const password = process.env.SEED_DEMO_PASSWORD
  if (!password) throw new Error('Thiếu SEED_DEMO_PASSWORD.')
  await page.goto('/login')
  await page
    .getByRole('textbox', { name: 'Email', exact: true })
    .fill('demo@meeting.local')
  await page.getByLabel('Mật khẩu', { exact: true }).fill(password)
  const response = page.waitForResponse(
    (r) =>
      r.url().endsWith('/api/v1/auth/login') && r.request().method() === 'POST',
  )
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  expect((await response).status()).toBe(200)
  await expect(page).toHaveURL(/\/meetings$/)
}

export const test = base.extend<{ signedIn: void }>({
  signedIn: [
    async ({ page }, use) => {
      await login(page)
      await use()
    },
    { auto: true },
  ],
})
export { expect }
