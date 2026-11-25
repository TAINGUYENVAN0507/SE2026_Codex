import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it, vi } from 'vitest'
import fixture from '../../../../contracts/fixtures/api/meeting_processing.json'
import { MeetingDetailPage } from '../../pages/MeetingDetailPage'
import { handlers, resetMockMeetings } from '../../mocks/handlers'
import { DemoStore } from './DemoStore'
import {
  getMeeting,
  listMeetings,
  patchMeeting,
  type MeetingDetail,
} from '../../api/client'

const server = setupServer(...handlers)
const clients: QueryClient[] = []
const meeting = { ...fixture, status: 'ready' as const }
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(async () => {
  cleanup()
  for (const client of clients.splice(0)) {
    await client.cancelQueries()
    client.clear()
  }
  server.resetHandlers()
  resetMockMeetings()
  vi.restoreAllMocks()
})
afterAll(() => server.close())
function renderPage(id = meeting.id) {
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
  server.use(
    http.get('*/api/v1/meetings/:id', () => HttpResponse.json(meeting)),
  )
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  })
  clients.push(client)
  render(
    <QueryClientProvider client={client}>
      <DemoStore>
        <MemoryRouter initialEntries={[`/meetings/${id}`]}>
          <Routes>
            <Route
              path="/meetings/:meetingId"
              element={<MeetingDetailPage />}
            />
          </Routes>
        </MemoryRouter>
      </DemoStore>
    </QueryClientProvider>,
  )
  return client
}
async function editTitle(value: string) {
  const user = userEvent.setup()
  await user.click(
    await screen.findByRole('button', { name: 'Đổi tên cuộc họp' }),
  )
  const field = screen.getByRole('textbox', { name: 'Tên cuộc họp' })
  await user.clear(field)
  await user.type(field, value)
  await user.click(screen.getByRole('button', { name: 'Lưu tên cuộc họp' }))
  return field
}

it('FE-02: đổi tên gửi đúng một PATCH title/version và dùng tên server trả về', async () => {
  const requests: unknown[] = []
  server.use(
    http.patch('*/api/v1/meetings/:id', async ({ params, request }) => {
      expect(params.id).toBe(meeting.id)
      requests.push(await request.json())
      return HttpResponse.json({
        ...meeting,
        title: 'Tên đã chuẩn hóa từ server',
        version: 2,
      })
    }),
  )
  const client = renderPage()
  await editTitle('Tên người dùng nhập')
  await waitFor(() =>
    expect(requests).toEqual([{ title: 'Tên người dùng nhập', version: 1 }]),
  )
  expect(
    await screen.findByRole('heading', { name: 'Tên đã chuẩn hóa từ server' }),
  ).toBeVisible()
  expect(
    client.getQueryData<MeetingDetail>(['meeting', meeting.id])?.version,
  ).toBe(2)
})

it.each([
  {
    status: 409,
    code: 'VERSION_CONFLICT',
    message: 'Dữ liệu đã được thay đổi ở nơi khác.',
  },
  { status: 422, code: 'VALIDATION_ERROR', message: 'Thông tin chưa hợp lệ.' },
])(
  'FE-02: đổi tên gặp $status giữ tên cũ, báo lỗi và giữ ô sửa',
  async ({ status, code, message }) => {
    const requests: unknown[] = []
    server.use(
      http.patch('*/api/v1/meetings/:id', async ({ request }) => {
        requests.push(await request.json())
        return HttpResponse.json(
          {
            error: {
              code,
              message: 'Lỗi tổng hợp',
              details: null,
              request_id: null,
            },
          },
          { status },
        )
      }),
    )
    const client = renderPage()
    const field = await editTitle('Tên chưa lưu')
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(field).toBeVisible()
    expect(field).toHaveValue('Tên chưa lưu')
    expect(field).toBeEnabled()
    expect(screen.getByText(meeting.title, { exact: true })).toBeVisible()
    expect(
      client.getQueryData<MeetingDetail>(['meeting', meeting.id])?.title,
    ).toBe(meeting.title)
    expect(requests).toEqual([{ title: 'Tên chưa lưu', version: 1 }])
  },
)

it('FE-02: đổi tên demo vẫn chỉ lưu trong phiên, không gửi PATCH', async () => {
  const requests: unknown[] = []
  server.use(
    http.patch('*/api/v1/meetings/:id', async ({ request }) => {
      requests.push(await request.json())
      return HttpResponse.json(meeting)
    }),
  )
  renderPage('sprint-42')
  await editTitle('Tên demo mới')
  expect(
    await screen.findByRole('heading', { name: 'Tên demo mới' }),
  ).toBeVisible()
  expect(requests).toEqual([])
})

it('FE-02: chặn lưu lặp lúc đang chờ và lần đổi tên sau dùng version server mới', async () => {
  const requests: { title: string; version: number }[] = []
  let release!: () => void
  const held = new Promise<void>((resolve) => {
    release = resolve
  })
  server.use(
    http.patch('*/api/v1/meetings/:id', async ({ request }) => {
      const body = (await request.json()) as { title: string; version: number }
      requests.push(body)
      if (requests.length === 1) await held
      return HttpResponse.json({
        ...meeting,
        title: body.title,
        version: body.version + 1,
      })
    }),
  )
  renderPage()
  const field = await editTitle('Tên lần một')
  try {
    await waitFor(() => expect(requests).toHaveLength(1))
    expect(field).toBeDisabled()
    expect(
      within(field.closest('form')!).getByRole('status'),
    ).toHaveTextContent('Đang lưu tên')
    fireEvent.submit(field.closest('form')!)
    expect(requests).toHaveLength(1)
  } finally {
    release()
  }
  expect(
    await screen.findByRole('heading', { name: 'Tên lần một' }),
  ).toBeVisible()
  await editTitle('Tên lần hai')
  expect(
    await screen.findByRole('heading', { name: 'Tên lần hai' }),
  ).toBeVisible()
  expect(requests).toEqual([
    { title: 'Tên lần một', version: 1 },
    { title: 'Tên lần hai', version: 2 },
  ])
})

it('FE-02: API mock giữ tên/version mới trong phiên và tìm theo tên mới', async () => {
  const title = 'Họp_đổi tên 100%'
  const saved = await patchMeeting(meeting.id, { title, version: 1 })
  expect(saved.title).toBe(title)
  expect(saved.version).toBe(2)
  expect((await getMeeting(meeting.id)).title).toBe(title)
  expect(
    (await listMeetings(1, undefined, '100%')).items.map((item) => item.id),
  ).toEqual([meeting.id])
})
