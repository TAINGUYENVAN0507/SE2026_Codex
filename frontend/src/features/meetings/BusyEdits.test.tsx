import { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest'
import type { MeetingDetail, TranscriptData } from '../../api/client'
import { handlers, resetMockMeetings } from '../../mocks/handlers'
import { apiMeetingToView } from './apiModel'
import { Transcript } from './Transcript'
import { RemoteSummary } from './RemoteSummary'
import { DeleteMeetingButton } from './DeleteMeetingButton'
import { DemoStore } from './DemoStore'
import meeting from '../../../../contracts/fixtures/api/meeting_processing.json'
import transcript from '../../../../contracts/fixtures/api/transcript_ready.json'
import summary from '../../../../contracts/fixtures/api/summary_ready.json'

const server = setupServer(...handlers)
const clients: QueryClient[] = []
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(async () => {
  cleanup()
  for (const client of clients.splice(0)) {
    await client.cancelQueries()
    client.clear()
  }
  server.resetHandlers()
  resetMockMeetings()
})
afterAll(() => server.close())
const view = () =>
  apiMeetingToView(meeting as MeetingDetail, transcript as TranscriptData)
function Harness() {
  const [data, setData] = useState(view)
  return (
    <Transcript
      meeting={data}
      position={0}
      onSeek={() => {}}
      onUpdate={(transform) => setData(transform)}
    />
  )
}
function wrap(children: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  clients.push(client)
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <DemoStore>{children}</DemoStore>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}
const busy = () =>
  HttpResponse.json(
    { error: { code: 'SERVICE_UNAVAILABLE', message: 'CANARY_RAW' } },
    { status: 503 },
  )

it('AD-018: transcript gặp 503 giữ draft/version và thử lưu lại thành công', async () => {
  const versions: number[] = []
  server.use(
    http.patch(
      '*/api/v1/meetings/:id/segments/:segment',
      async ({ request }) => {
        const body = (await request.json()) as { text: string; version: number }
        versions.push(body.version)
        return versions.length === 1
          ? busy()
          : HttpResponse.json({
              ...transcript.segments[0],
              text: body.text,
              version: body.version + 1,
              is_edited: true,
            })
      },
    ),
  )
  render(<Harness />)
  const user = userEvent.setup()
  await user.click(
    screen.getByRole('button', {
      name: `Sửa đoạn ${transcript.segments[0].id}`,
    }),
  )
  const field = screen.getByRole('textbox', { name: 'Chỉnh sửa transcript' })
  fireEvent.change(field, {
    target: { value: 'Nội dung cần giữ khi máy chủ bận' },
  })
  await user.click(screen.getByRole('button', { name: 'Lưu thay đổi' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Máy chủ đang bận')
  expect(field).toHaveValue('Nội dung cần giữ khi máy chủ bận')
  expect(versions).toHaveLength(1)
  await user.click(screen.getByRole('button', { name: 'Thử lưu lại' }))
  expect(
    await screen.findByText('Nội dung cần giữ khi máy chủ bận'),
  ).toBeInTheDocument()
  expect(versions).toEqual([
    transcript.segments[0].version,
    transcript.segments[0].version,
  ])
})

it('AD-018: đổi tên speaker gặp 503 giữ tên đã gõ và cho thử lại', async () => {
  let requests = 0
  server.use(
    http.patch(
      '*/api/v1/meetings/:id/speakers/:speaker',
      async ({ request }) => {
        const body = (await request.json()) as {
          display_name: string
          version: number
        }
        return ++requests === 1
          ? busy()
          : HttpResponse.json({
              ...transcript.speakers[0],
              display_name: body.display_name,
              version: body.version + 1,
            })
      },
    ),
  )
  render(<Harness />)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Đổi tên Chị Lan (PM)' }))
  const field = screen.getByRole('textbox', {
    name: 'Tên mới của Chị Lan (PM)',
  })
  fireEvent.change(field, { target: { value: 'Tên mới cần giữ' } })
  await user.click(screen.getByRole('button', { name: 'Lưu' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Máy chủ đang bận')
  expect(field).toHaveValue('Tên mới cần giữ')
  expect(requests).toBe(1)
  await user.click(screen.getByRole('button', { name: 'Thử lưu tên lại' }))
  expect(
    (await screen.findAllByText('Tên mới cần giữ')).length,
  ).toBeGreaterThan(0)
  expect(requests).toBe(2)
})

it('AD-018: summary gặp 503 giữ bản nháp và cho thử lưu lại', async () => {
  let requests = 0
  server.use(
    http.put('*/api/v1/meetings/:id/summary', async ({ request }) => {
      const body = (await request.json()) as { content: typeof summary.content }
      return ++requests === 1
        ? busy()
        : HttpResponse.json({
            ...summary,
            content: body.content,
            version: summary.version + 1,
          })
    }),
  )
  wrap(<RemoteSummary meeting={view()} onSeek={() => {}} />)
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: 'Chỉnh sửa' }))
  const field = screen.getByRole('textbox', { name: 'Chỉnh sửa tổng quan' })
  fireEvent.change(field, { target: { value: 'Tổng quan cần giữ' } })
  await user.click(screen.getByRole('button', { name: 'Lưu' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Máy chủ đang bận')
  expect(field).toHaveValue('Tổng quan cần giữ')
  expect(requests).toBe(1)
  await user.click(screen.getByRole('button', { name: 'Thử lưu tóm tắt lại' }))
  expect(await screen.findByText('Tổng quan cần giữ')).toBeInTheDocument()
})

it('AD-018: chạy lại job gặp 503 chỉ gửi lại khi người dùng bấm', async () => {
  let requests = 0
  server.use(
    http.get('*/api/v1/meetings/:id/summary', () =>
      HttpResponse.json({ ...summary, status: 'failed', content: null }),
    ),
    http.post('*/api/v1/meetings/:id/jobs', () => {
      requests++
      return busy()
    }),
  )
  wrap(<RemoteSummary meeting={view()} onSeek={() => {}} />)
  const user = userEvent.setup()
  await user.click(
    await screen.findByRole('button', { name: 'Tạo lại tóm tắt' }),
  )
  expect(await screen.findByRole('alert')).toHaveTextContent('Máy chủ đang bận')
  expect(requests).toBe(1)
  await user.click(screen.getByRole('button', { name: 'Thử tạo lại tóm tắt' }))
  expect(requests).toBe(2)
})

it('AD-018: xóa gặp 503 giữ hộp xác nhận, không tự gửi lại', async () => {
  let requests = 0
  server.use(
    http.delete('*/api/v1/meetings/:id', () => {
      requests++
      return busy()
    }),
  )
  wrap(<DeleteMeetingButton meetingId={meeting.id} />)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Xóa cuộc họp' }))
  await user.click(screen.getByRole('button', { name: 'Xóa vĩnh viễn' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Máy chủ đang bận')
  expect(requests).toBe(1)
  expect(screen.getByRole('alertdialog')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Thử xóa lại' }))
  expect(requests).toBe(2)
})
