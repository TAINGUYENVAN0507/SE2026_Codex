import { test, expect, type BrowserContext } from '@playwright/test'
import meeting from '../../contracts/fixtures/api/meeting_processing.json' with { type: 'json' }
import transcript from '../../contracts/fixtures/api/transcript_ready.json' with { type: 'json' }
import user from '../../contracts/fixtures/api/user_me.json' with { type: 'json' }
import config from '../../contracts/fixtures/api/config.json' with { type: 'json' }
import summary from '../../contracts/fixtures/api/summary_disabled.json' with { type: 'json' }

async function fakeApi(context: BrowserContext, holdFirst = false) {
  let text = 'Bản gốc kiểm thử tự tạo'
  let version = 1
  let seen!: () => void
  let release!: () => void
  const entered = new Promise<void>((resolve) => {
    seen = resolve
  })
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  let calls = 0
  await context.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const respond = (body: unknown, status = 200) =>
      route.fulfill({ status, json: body })
    if (path.endsWith('/auth/me')) return respond(user)
    if (path.endsWith('/config')) return respond(config)
    if (route.request().method() === 'PATCH') {
      calls += 1
      const patch = route.request().postDataJSON() as {
        text: string
        version: number
      }
      if (holdFirst && calls === 1) {
        seen()
        await gate
      }
      if (patch.version !== version)
        return respond(
          { error: { code: 'VERSION_CONFLICT', message: 'Xung đột' } },
          409,
        )
      text = patch.text
      version += 1
      return respond({
        ...transcript.segments[0],
        text,
        version,
        is_edited: true,
      })
    }
    if (path.endsWith('/transcript'))
      return respond({
        ...transcript,
        segments: [{ ...transcript.segments[0], text, version }],
      })
    if (path.endsWith('/summary')) return respond(summary)
    if (path.endsWith('/action-items')) return respond({ items: [] })
    if (path.endsWith('/' + meeting.id))
      return respond({ ...meeting, status: 'ready', latest_job_id: null })
    return respond(
      { error: { code: 'NOT_FOUND', message: 'Fixture không có' } },
      404,
    )
  })
  return { entered, release, text: () => text, version: () => version }
}

test('TC16 browser: A response chậm không ghi đè C; reload đọc C', async ({
  page,
  context,
}) => {
  const api = await fakeApi(context, true)
  await page.goto('/meetings/' + meeting.id)
  await page
    .getByRole('button', { name: 'Sửa đoạn ' + transcript.segments[0].id })
    .click()
  const field = page.getByRole('textbox', { name: 'Chỉnh sửa transcript' })
  await field.fill('Bản A')
  await api.entered
  await field.fill('Bản C mới nhất')
  api.release()
  await expect.poll(api.text).toBe('Bản C mới nhất')
  await expect(field).toHaveValue('Bản C mới nhất')
  await page.reload()
  await expect(page.getByText('Bản C mới nhất', { exact: true })).toBeVisible()
})

test('TC17 browser: hai tab, tab cũ 409 và giữ draft', async ({
  page,
  context,
}) => {
  const api = await fakeApi(context)
  const other = await context.newPage()
  for (const tab of [page, other]) {
    await tab.goto('/meetings/' + meeting.id)
    await tab
      .getByRole('button', { name: 'Sửa đoạn ' + transcript.segments[0].id })
      .click()
  }
  await page
    .getByRole('textbox', { name: 'Chỉnh sửa transcript' })
    .fill('Đã lưu từ tab A')
  await expect.poll(api.version).toBe(2)
  const field = other.getByRole('textbox', { name: 'Chỉnh sửa transcript' })
  await field.fill('Draft tab B cần giữ')
  await expect(other.getByRole('alertdialog')).toBeVisible()
  await expect(field).toHaveValue('Draft tab B cần giữ')
  expect(api.text()).toBe('Đã lưu từ tab A')
  await other.close()
})
