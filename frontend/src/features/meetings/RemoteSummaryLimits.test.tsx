import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it, vi } from 'vitest'
import ready from '../../../../contracts/fixtures/api/summary_ready.json'
import meetingFixture from '../../../../contracts/fixtures/api/meeting_processing.json'
import transcriptFixture from '../../../../contracts/fixtures/api/transcript_ready.json'
import { apiMeetingToView } from './apiModel'
import { RemoteSummary } from './RemoteSummary'
import type { MeetingDetail, TranscriptData } from '../../api/client'

const server = setupServer()
const clients: QueryClient[] = []
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(async () => {
  cleanup()
  for (const client of clients.splice(0)) {
    await client.cancelQueries()
    client.clear()
  }
  server.resetHandlers()
})
afterAll(() => server.close())
function renderSummary() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  })
  clients.push(client)
  render(
    <QueryClientProvider client={client}>
      <RemoteSummary
        meeting={apiMeetingToView(
          meetingFixture as MeetingDetail,
          transcriptFixture as TranscriptData,
        )}
        onSeek={vi.fn()}
      />
    </QueryClientProvider>,
  )
}

it.each([
  { field: 'key_points', label: 'ý chính', input: 'Ý chính' },
  { field: 'decisions', label: 'quyết định', input: 'Quyết định' },
] as const)(
  'FE-12: dừng ở 50 $label, xóa còn 49 thì thêm được',
  async ({ field, label, input }) => {
    server.use(
      http.get('*/api/v1/meetings/:id/summary', () =>
        HttpResponse.json({
          ...ready,
          content: {
            ...ready.content,
            [field]: Array.from({ length: 50 }, (_, i) => ({
              text: `Mục ${i + 1}`,
              evidence_segment_ids: [],
            })),
          },
        }),
      ),
    )
    const user = userEvent.setup()
    renderSummary()
    await user.click(await screen.findByRole('button', { name: 'Chỉnh sửa' }))
    const add = screen.getByRole('button', { name: `Thêm ${label}` })
    expect(add).toBeDisabled()
    expect(
      screen.getByText(new RegExp(`Đã đạt giới hạn 50 ${label}`)),
    ).toBeVisible()
    await user.click(add)
    expect(
      screen.getAllByRole('textbox', { name: new RegExp(`^${input} [0-9]+$`) }),
    ).toHaveLength(50)
    await user.click(screen.getByRole('button', { name: `Xóa ${field} 50` }))
    expect(add).toBeEnabled()
    expect(
      screen.queryByText(new RegExp(`Đã đạt giới hạn 50 ${label}`)),
    ).not.toBeInTheDocument()
    await user.click(add)
    expect(screen.getByRole('textbox', { name: `${input} 50` })).toBeVisible()
    expect(add).toBeDisabled()
    expect(
      screen.getAllByRole('textbox', { name: new RegExp(`^${input} [0-9]+$`) }),
    ).toHaveLength(50)
  },
)

it('FE-12: dán tổng quan vượt giới hạn chỉ gửi đúng 5000 ký tự', async () => {
  const lengths: number[] = []
  server.use(
    http.get('*/api/v1/meetings/:id/summary', () => HttpResponse.json(ready)),
    http.put('*/api/v1/meetings/:id/summary', async ({ request }) => {
      const body = (await request.json()) as {
        content: typeof ready.content
        version: number
      }
      lengths.push(body.content.overview.length)
      return body.content.overview.length > 5000
        ? HttpResponse.json(
            { error: { code: 'VALIDATION_ERROR', message: 'Quá dài' } },
            { status: 422 },
          )
        : HttpResponse.json({
            ...ready,
            content: body.content,
            version: body.version + 1,
            is_edited: true,
          })
    }),
  )
  const user = userEvent.setup()
  renderSummary()
  await user.click(await screen.findByRole('button', { name: 'Chỉnh sửa' }))
  const field = screen.getByRole('textbox', { name: 'Chỉnh sửa tổng quan' })
  await user.clear(field)
  await user.paste('x'.repeat(5001))
  await user.click(screen.getByRole('button', { name: 'Lưu' }))
  await waitFor(() => expect(lengths).toEqual([5000]))
  expect(field).toHaveAttribute('maxlength', '5000')
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

it.each([
  { field: 'key_points', input: 'Ý chính', pasted: 1001 },
  { field: 'decisions', input: 'Quyết định', pasted: 1001 },
  { field: 'key_points', input: 'Ý chính', pasted: 1000 },
  { field: 'decisions', input: 'Quyết định', pasted: 1000 },
] as const)(
  'FE-12: $input dán $pasted ký tự chỉ lưu đúng 1000',
  async ({ field, input, pasted }) => {
    const texts: string[] = []
    server.use(
      http.get('*/api/v1/meetings/:id/summary', () => HttpResponse.json(ready)),
      http.put('*/api/v1/meetings/:id/summary', async ({ request }) => {
        const body = (await request.json()) as {
          content: typeof ready.content
          version: number
        }
        texts.push(body.content[field][0].text)
        return body.content[field][0].text.length > 1000
          ? HttpResponse.json(
              { error: { code: 'VALIDATION_ERROR', message: 'Quá dài' } },
              { status: 422 },
            )
          : HttpResponse.json({
              ...ready,
              content: body.content,
              version: body.version + 1,
            })
      }),
    )
    const user = userEvent.setup()
    renderSummary()
    await user.click(await screen.findByRole('button', { name: 'Chỉnh sửa' }))
    const item = screen.getByRole('textbox', { name: `${input} 1` })
    await user.clear(item)
    await user.paste('x'.repeat(pasted))
    await user.click(screen.getByRole('button', { name: 'Lưu' }))
    await waitFor(() => expect(texts).toEqual(['x'.repeat(1000)]))
    expect(
      await screen.findByRole('button', { name: 'Chỉnh sửa' }),
    ).toBeEnabled()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  },
)

it.each(['key_points', 'decisions'] as const)(
  'FE-12: đọc được ý dài đã lưu (%s), chặn gửi cho đến khi rút còn 1000',
  async (field) => {
    let requests = 0
    server.use(
      http.get('*/api/v1/meetings/:id/summary', () =>
        HttpResponse.json({
          ...ready,
          content: {
            ...ready.content,
            [field]: [{ text: 'x'.repeat(1001), evidence_segment_ids: [] }],
          },
        }),
      ),
      http.put('*/api/v1/meetings/:id/summary', () => {
        requests++
        return HttpResponse.json(ready)
      }),
    )
    const user = userEvent.setup()
    renderSummary()
    expect(await screen.findByText('x'.repeat(1001))).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Chỉnh sửa' }))
    await user.click(screen.getByRole('button', { name: 'Lưu' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Tổng quan và mỗi ý cần có nội dung hợp lệ.',
    )
    expect(requests).toBe(0)
    expect(
      screen.getByRole('textbox', {
        name: `${field === 'key_points' ? 'Ý chính' : 'Quyết định'} 1`,
      }),
    ).toHaveValue('x'.repeat(1001))
  },
)
