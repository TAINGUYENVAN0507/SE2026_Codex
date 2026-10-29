import { test, expect } from '../fixtures.js'

test('Đăng nhập demo qua API thật và thấy danh sách cuộc họp', async ({
  page,
}) => {
  await expect(
    page.getByRole('heading', { name: 'Cuộc họp', exact: true }),
  ).toBeVisible()
  const session = await page.request.get('/api/v1/auth/me')
  expect(session.status()).toBe(200)
  expect((await session.json()).user.email).toBe('demo@meeting.local')
  expect(
    await page.evaluate(() =>
      navigator.serviceWorker.getRegistrations().then((items) => items.length),
    ),
  ).toBe(0)
})
