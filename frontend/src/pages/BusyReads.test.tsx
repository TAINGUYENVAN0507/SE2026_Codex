import { useQueryClient, type QueryClient } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useEffect } from 'react'
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
import App from '../App'
import { AppProviders } from '../app/AppProviders'
import { handlers, resetMockMeetings } from '../mocks/handlers'
import { resetMockAuth } from '../mocks/auth'
import user from '../../../contracts/fixtures/api/user_me.json'
import list from '../../../contracts/fixtures/api/meeting_list.json'
import meeting from '../../../contracts/fixtures/api/meeting_processing.json'
import transcript from '../../../contracts/fixtures/api/transcript_ready.json'

const server = setupServer(...handlers)
const clients: QueryClient[] = []
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
beforeEach(() =>
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {}),
)
afterAll(() => server.close())
afterEach(async () => {
  cleanup()
  for (const client of clients.splice(0)) {
    await client.cancelQueries()
    client.clear()
  }
  server.resetHandlers()
  resetMockAuth()
  resetMockMeetings()
  vi.useRealTimers()
  vi.restoreAllMocks()
  window.history.replaceState({}, '', '/')
})

const readyMeeting = {
  ...meeting,
  status: 'ready',
  latest_job: null,
  latest_job_id: null,
}
const busy = () =>
  HttpResponse.json(
    { error: { code: 'SERVICE_UNAVAILABLE', message: 'CANARY_RAW' } },
    { status: 503, headers: { 'Retry-After': '0' } },
  )
function setup(path: string) {
  vi.useFakeTimers()
  window.history.replaceState({}, '', path)
  let captured!: QueryClient
  function Capture() {
    const client = useQueryClient()
    useEffect(() => {
      captured = client
      clients.push(client)
    }, [client])
    return null
  }
  const view = render(
    <AppProviders>
      <Capture />
    </AppProviders>,
  )
  captured.setQueryData(['me'], user)
  view.rerender(
    <AppProviders>
      <Capture />
      <button>Điều khiển ngoài nội dung</button>
      <App />
    </AppProviders>,
  )
  return captured
}
async function advance(ms = 100) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

it('AD-018: danh sách hết hai retry hiện bận, bấm thử lại lấy được dữ liệu', async () => {
  let requests = 0
  let available = false
  server.use(
    http.get('*/api/v1/meetings', () => {
      requests++
      return available ? HttpResponse.json(list) : busy()
    }),
  )
  setup('/meetings')
  const search = screen.getByRole('textbox', { name: 'Tìm cuộc họp' })
  search.focus()
  await advance()
  expect(search).toHaveFocus()
  expect(requests).toBe(3)
  expect(screen.getByRole('alert')).toHaveTextContent('Máy chủ đang bận')
  expect(screen.queryByText('CANARY_RAW')).not.toBeInTheDocument()
  const retry = screen.getByRole('button', { name: 'Thử lại' })
  available = true
  fireEvent.click(retry)
  await advance()
  expect(screen.getByText(list.items[0].title)).toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  expect(requests).toBe(4)
})

it.each(['meeting', 'transcript'] as const)(
  'AD-018: chi tiết lỗi %s có thử lại ngay trên trang và phục hồi',
  async (target) => {
    let requests = 0
    let available = false
    server.use(
      http.get('*/api/v1/meetings/:id', () => {
        if (target !== 'meeting') return HttpResponse.json(readyMeeting)
        requests++
        return available ? HttpResponse.json(readyMeeting) : busy()
      }),
      http.get('*/api/v1/meetings/:id/transcript', () => {
        if (target !== 'transcript') return HttpResponse.json(transcript)
        requests++
        return available ? HttpResponse.json(transcript) : busy()
      }),
    )
    setup(`/meetings/${meeting.id}`)
    const control = screen.getByRole('button', {
      name: 'Điều khiển ngoài nội dung',
    })
    control.focus()
    await advance()
    expect(control).toHaveFocus()
    expect(screen.getByRole('main')).toBeInTheDocument()
    expect(requests).toBe(3)
    expect(screen.getByRole('alert')).toHaveTextContent('Máy chủ đang bận')
    expect(
      screen.queryByRole('status', {
        name: 'Đang tải cuộc họp và transcript…',
      }),
    ).not.toBeInTheDocument()
    expect(screen.queryByText('CANARY_RAW')).not.toBeInTheDocument()
    const retry = screen.getByRole('button', { name: 'Thử lại' })
    available = true
    fireEvent.click(retry)
    await advance()
    expect(
      screen.getByRole('heading', { name: meeting.title }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(requests).toBe(4)
  },
)
