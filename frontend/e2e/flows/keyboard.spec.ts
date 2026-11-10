import { test, expect, type Page, type Locator } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { syntheticWav } from '../audio.js'

async function tabTo(page: Page, target: Locator) {
  await expect(target).toBeVisible()
  for (let step = 0; step < 80; step++) {
    if (
      await target.evaluate((element) => element === document.activeElement)
    ) {
      await expect(target).toBeFocused()
      const visible = await target.evaluate((element) => {
        if (!element.matches(':focus-visible')) return false
        const ring = element.closest('.search-input') || element
        const style = getComputedStyle(ring)
        return (
          parseFloat(style.outlineWidth) >= 2 && style.outlineStyle !== 'none'
        )
      })
      expect(visible, 'Phải nhìn thấy focus bằng bàn phím').toBe(true)
      return
    }
    await page.keyboard.press('Tab')
  }
  throw new Error('Không tới được control bằng Tab trong 80 bước.')
}

test('FE-16: chỉ bàn phím đăng nhập, upload, mở lại meeting và export', async ({
  page,
}, testInfo) => {
  const password =
    process.env.KEYBOARD_E2E_PASSWORD || process.env.SEED_DEMO_PASSWORD
  if (!password) throw new Error('Thiếu SEED_DEMO_PASSWORD cho E2E riêng.')
  await page.goto('/login')
  await tabTo(page, page.getByRole('textbox', { name: 'Email', exact: true }))
  await page.keyboard.type(
    process.env.KEYBOARD_E2E_EMAIL || 'demo@meeting.local',
  )
  await tabTo(page, page.getByLabel('Mật khẩu', { exact: true }))
  await page.keyboard.type(password)
  await tabTo(
    page,
    page.getByRole('button', { name: 'Đăng nhập', exact: true }),
  )
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/meetings$/)
  await tabTo(
    page,
    page.getByRole('link', { name: 'Cuộc họp mới', exact: true }),
  )
  await page.keyboard.press('Enter')
  const chooserButton = page.getByRole('button', { name: 'Chọn file trên máy' })
  await expect(chooserButton).toBeEnabled()
  await tabTo(page, chooserButton)
  const choosing = page.waitForEvent('filechooser')
  await page.keyboard.press('Enter')
  // Thay thao tác hộp thoại chọn file của OS bằng API filechooser; không dùng chuột.
  await (await choosing).setFiles(syntheticWav(30))
  const title = `Keyboard ${Date.now()}`
  await tabTo(page, page.getByRole('textbox', { name: 'Tên cuộc họp' }))
  await page.keyboard.press('ControlOrMeta+A')
  await page.keyboard.type(title)
  await tabTo(
    page,
    page.getByRole('checkbox', { name: /Tôi xác nhận đã có sự đồng ý/ }),
  )
  await page.keyboard.press('Space')
  await tabTo(
    page,
    page.getByRole('button', { name: 'Tạo biên bản', exact: true }),
  )
  await testInfo.attach('keyboard-focus-upload', {
    body: await page.screenshot(),
    contentType: 'image/png',
  })
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/meetings\/[0-9a-f-]+$/)
  const id = new URL(page.url()).pathname.split('/').pop()!
  try {
    await expect(
      page.getByRole('button', { name: 'Xuất biên bản', exact: true }),
    ).toBeEnabled({ timeout: 90_000 })
    await tabTo(page, page.getByRole('link', { name: 'Cuộc họp', exact: true }))
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/meetings$/)
    await tabTo(page, page.getByRole('textbox', { name: 'Tìm cuộc họp' }))
    await page.keyboard.type(title)
    await tabTo(page, page.getByRole('link', { name: new RegExp(title) }))
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(new RegExp(`/meetings/${id}$`))
    const trigger = page.getByRole('button', {
      name: 'Xuất biên bản',
      exact: true,
    })
    await expect(trigger).toBeEnabled()
    await tabTo(page, trigger)
    await page.keyboard.press('Enter')
    await tabTo(
      page,
      page.getByRole('button', { name: 'Dữ liệu (.json)', exact: true }),
    )
    const downloading = page.waitForEvent('download')
    await page.keyboard.press('Enter')
    const downloaded = await downloading
    const content = JSON.parse(
      await readFile((await downloaded.path())!, 'utf8'),
    )
    expect(content.meeting.id).toBe(id)
    await expect(trigger).toBeFocused()
  } finally {
    const deleted = await page.request.delete(`/api/v1/meetings/${id}`)
    expect(deleted.status()).toBe(204)
  }
})
