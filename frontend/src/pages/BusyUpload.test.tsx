import { FetchXHR } from '../test/FetchXHR'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import {
  afterAll,
  afterEach,
  beforeAll,
  beforeEach,
  expect,
  it,
  vi,
} from 'vitest'
import { NewMeetingPage } from './NewMeetingPage'
import { DemoStore } from '../features/meetings/DemoStore'
import user from '../../../contracts/fixtures/api/user_me.json'
import config from '../../../contracts/fixtures/api/config.json'
import created from '../../../contracts/fixtures/api/meeting_created.json'

const server = setupServer()
const clients: QueryClient[] = []
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
beforeEach(() => {
  vi.stubGlobal('XMLHttpRequest', FetchXHR)
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:busy-test')
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
})
afterEach(async () => {
  cleanup()
  for (const client of clients.splice(0)) {
    await client.cancelQueries()
    client.clear()
  }
  server.resetHandlers()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})
afterAll(() => server.close())

function setup() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  client.setQueryData(['me'], user)
  client.setQueryData(['config'], config)
  clients.push(client)
  render(
    <QueryClientProvider client={client}>
      <DemoStore>
        <MemoryRouter initialEntries={['/meetings/new']}>
          <Routes>
            <Route path="/meetings/new" element={<NewMeetingPage />} />
            <Route path="/meetings/:id" element={<h1>Chi tiết vừa tạo</h1>} />
          </Routes>
        </MemoryRouter>
      </DemoStore>
    </QueryClientProvider>,
  )
  fireEvent.change(screen.getByLabelText('Chọn file audio'), {
    target: {
      files: [new File(['synthetic'], 'busy.wav', { type: 'audio/wav' })],
    },
  })
  fireEvent.click(
    screen.getByRole('checkbox', { name: /Tôi xác nhận đã có sự đồng ý/ }),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Tạo biên bản' }))
}

function busy(retryAfter = '0') {
  return HttpResponse.json(
    {
      error: {
        code: 'SERVICE_UNAVAILABLE',
        message: 'CANARY_RAW',
        details: null,
        request_id: null,
      },
    },
    { status: 503, headers: { 'Retry-After': retryAfter } },
  )
}

it('AD-018: hai lần bận rồi tạo đúng một meeting, ba request cùng key', async () => {
  const keys: (string | null)[] = []
  let meetings = 0
  server.use(
    http.post('*/api/v1/meetings', ({ request }) => {
      keys.push(request.headers.get('Idempotency-Key'))
      if (keys.length < 3) return busy()
      meetings++
      return HttpResponse.json(created, { status: 201 })
    }),
  )
  setup()
  await waitFor(() => expect(keys).toHaveLength(3), { timeout: 5000 })
  expect(
    await screen.findByRole('heading', { name: 'Chi tiết vừa tạo' }),
  ).toBeInTheDocument()
  expect(keys).toHaveLength(3)
  expect(new Set(keys).size).toBe(1)
  expect(keys[0]).toBeTruthy()
  expect(meetings).toBe(1)
})

it('AD-018: bốn lần 503 hiện thử lại thủ công, giữ file và cùng key', async () => {
  const keys: (string | null)[] = []
  server.use(
    http.post('*/api/v1/meetings', ({ request }) => {
      keys.push(request.headers.get('Idempotency-Key'))
      return keys.length <= 4
        ? busy()
        : HttpResponse.json(created, { status: 201 })
    }),
  )
  setup()
  const retry = await screen.findByRole(
    'button',
    { name: 'Thử tải lại' },
    { timeout: 5000 },
  )
  expect(keys).toHaveLength(4)
  expect(screen.getByRole('alert')).not.toHaveTextContent('CANARY_RAW')
  expect(screen.getByText('busy.wav')).toBeInTheDocument()
  fireEvent.click(retry)
  expect(
    await screen.findByRole('heading', { name: 'Chi tiết vừa tạo' }),
  ).toBeInTheDocument()
  expect(keys).toHaveLength(5)
  expect(new Set(keys).size).toBe(1)
})

it('AD-018: hủy trong lúc chờ Retry-After không gửi tiếp và không chuyển trang', async () => {
  let requests = 0
  server.use(
    http.post('*/api/v1/meetings', () => {
      requests++
      return busy('60')
    }),
  )
  setup()
  const cancel = screen.getByRole('button', { name: 'Hủy tải lên' })
  cancel.focus()
  await waitFor(() =>
    expect(
      screen.getByRole('status', { name: 'Trạng thái tải lên' }),
    ).toHaveTextContent(/Máy chủ đang bận.*60 giây/),
  )
  expect(cancel).toHaveFocus()
  fireEvent.click(cancel)
  expect(
    await screen.findByRole('button', { name: 'Tạo biên bản' }),
  ).toBeEnabled()
  expect(requests).toBe(1)
  expect(
    screen.queryByRole('heading', { name: 'Chi tiết vừa tạo' }),
  ).not.toBeInTheDocument()
})
