import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import axe from 'axe-core'
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
import { handlers, resetMockMeetings } from '../mocks/handlers'
import { resetMockAuth } from '../mocks/auth'
import userMe from '../../../contracts/fixtures/api/user_me.json'
import meeting from '../../../contracts/fixtures/api/meeting_processing.json'
import summary from '../../../contracts/fixtures/api/summary_ready.json'

const server = setupServer(...handlers)
const clients: QueryClient[] = []
const originalTitle = document.title
const originalLanguage = document.documentElement.lang
beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' })
  // Cùng metadata với index.html thật; jsdom không tải file index.
  document.title = 'Biên bản | Trợ lý cuộc họp tiếng Việt'
  document.documentElement.lang = 'vi'
})
beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
  server.use(
    http.get('*/api/v1/meetings/:id', () =>
      HttpResponse.json({
        ...meeting,
        status: 'ready',
        latest_job_id: null,
        latest_job: null,
      }),
    ),
  )
})
afterEach(async () => {
  cleanup()
  for (const client of clients.splice(0)) {
    await client.cancelQueries()
    client.clear()
  }
  server.resetHandlers()
  resetMockAuth()
  resetMockMeetings()
  vi.restoreAllMocks()
})
afterAll(() => {
  server.close()
  document.title = originalTitle
  document.documentElement.lang = originalLanguage
})

it.each([
  ['danh sách', '/meetings', 'Cuộc họp'],
  ['chi tiết', `/meetings/${meeting.id}`, meeting.title],
  ['upload', '/meetings/new', 'Tạo cuộc họp mới'],
  ['cài đặt', '/settings', 'Cài đặt'],
])(
  'FE-16 axe: %s không có vi phạm serious/critical',
  async (_name, path, heading) => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
    client.setQueryData(['me'], userMe)
    clients.push(client)
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[path]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    await screen.findByRole('heading', { name: heading })
    if (path.includes(meeting.id))
      await screen.findByText(summary.content.overview)
    if (path === '/meetings/new') await screen.findByText(/tối đa 200 MB/)
    // jsdom không có layout/canvas. Contrast được kiểm riêng bằng Chromium, không bỏ ở E2E.
    const result = await axe.run(document.documentElement, {
      rules: { 'color-contrast': { enabled: false } },
    })
    const blocking = result.violations.filter(
      (v) => v.impact === 'serious' || v.impact === 'critical',
    )
    expect(
      blocking.map((v) => ({
        id: v.id,
        impact: v.impact,
        targets: v.nodes.map((n) => n.target),
      })),
    ).toEqual([])
  },
  15_000,
)
