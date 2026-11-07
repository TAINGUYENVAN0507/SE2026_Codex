import { readFileSync } from 'node:fs'
import { test, expect } from '../fixtures.js'

test('FE-19: cài đặt mở từ điều hướng, reload được và chỉ bật xóa khi có contract', async ({
  page,
}) => {
  let deletions = 0
  page.on('request', (r) => {
    if (
      r.method() === 'DELETE' &&
      new URL(r.url()).pathname === '/api/v1/auth/me'
    )
      deletions++
  })
  await page
    .getByRole('link', { name: 'Cài đặt tài khoản', exact: true })
    .click()
  await expect(page).toHaveURL(/\/settings$/)
  await expect(
    page.getByRole('heading', { name: 'Cài đặt', exact: true }),
  ).toBeVisible()
  await expect(page.locator('.settings-profile')).toContainText(
    'demo@meeting.local',
  )
  await page.reload()
  await expect(
    page.getByRole('heading', { name: 'Cài đặt', exact: true }),
  ).toBeVisible()
  const contract = JSON.parse(
    readFileSync(
      new URL('../../../contracts/openapi.json', import.meta.url),
      'utf8',
    ),
  )
  const button = page.getByRole('button', {
    name: 'Xóa tài khoản',
    exact: true,
  })
  if (contract.paths['/api/v1/auth/me']?.delete)
    await expect(button).toBeEnabled()
  else {
    await expect(button).toBeDisabled()
    await expect(page.getByRole('status')).toContainText('hiện chưa khả dụng')
  }
  expect(deletions).toBe(0)
})
