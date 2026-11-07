import { readFile } from 'node:fs/promises'
import { expect, type Page } from '@playwright/test'

const labels = {
  txt: 'Văn bản (.txt)',
  md: 'Markdown (.md)',
  json: 'Dữ liệu (.json)',
} as const

export async function downloadExport(page: Page, format: keyof typeof labels) {
  await page.getByRole('button', { name: 'Xuất biên bản', exact: true }).click()
  const response = page.waitForResponse((r) => {
    const url = new URL(r.url())
    return (
      url.pathname.endsWith('/export') &&
      url.searchParams.get('format') === format
    )
  })
  const downloaded = page.waitForEvent('download')
  await page.getByRole('button', { name: labels[format], exact: true }).click()
  const result = await response
  expect(result.status(), await result.text()).toBe(200)
  expect(result.headers()['content-disposition']).toContain('attachment')
  const file = await downloaded
  expect(file.suggestedFilename()).toMatch(new RegExp(`\\.${format}$`))
  const filePath = await file.path()
  if (!filePath) throw new Error('Trình duyệt không tạo file tải xuống.')
  return readFile(filePath, 'utf8')
}
