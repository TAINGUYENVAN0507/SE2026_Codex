import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it, vi } from 'vitest'
import { JobStatusCard } from './JobStatusCard'
import job from '../../../../contracts/fixtures/api/job_retry_scheduled.json'

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
  vi.useRealTimers()
})
afterAll(() => server.close())
function setup() {
  vi.useFakeTimers()
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  clients.push(client)
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <JobStatusCard jobId={job.id} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}
const running = {
  ...job,
  status: 'running',
  progress: 0.65,
  started_at: null,
  next_run_at: null,
}
const busy = () =>
  HttpResponse.json(
    { error: { code: 'SERVICE_UNAVAILABLE', message: 'RAW_CANARY' } },
    { status: 503, headers: { 'Retry-After': '8' } },
  )

it('VT-018: 30 giây bận liên tục chỉ 5 request, giữ tiến độ đã biết', async () => {
  let requests = 0
  server.use(
    http.get('*/api/v1/jobs/:id', () =>
      ++requests === 1 ? HttpResponse.json(running) : busy(),
    ),
  )
  setup()
  await advance(100)
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '65')
  for (let i = 0; i < 30; i++) await advance(1000)
  expect(requests).toBe(5)
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '65')
  expect(screen.getByRole('alert')).toHaveTextContent(/kiểm tra lại sau 8 giây/)
})

it('VT-018: lỗi mạng lùi dần tối đa 10 giây, không dừng poll ở lỗi đầu', async () => {
  let requests = 0
  server.use(
    http.get('*/api/v1/jobs/:id', () =>
      ++requests === 1 ? HttpResponse.json(running) : HttpResponse.error(),
    ),
  )
  setup()
  await advance(100)
  for (let i = 0; i < 30; i++) await advance(1000)
  expect(requests).toBe(5)
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '65')
  expect(screen.getByRole('alert')).toHaveTextContent(/10 giây/)
})

it('VT-018: response 200 phục hồi nhịp 2 giây; job xong dừng poll', async () => {
  let requests = 0
  server.use(
    http.get('*/api/v1/jobs/:id', () => {
      requests++
      if (requests === 2) return busy()
      return HttpResponse.json({
        ...running,
        status: requests >= 4 ? 'succeeded' : 'running',
        progress: requests >= 4 ? 1 : 0.65,
      })
    }),
  )
  setup()
  await advance(100)
  await advance(2000)
  expect(requests).toBe(2)
  await advance(8000)
  expect(requests).toBe(3)
  await advance(2000)
  expect(requests).toBe(4)
  expect(screen.getByText('Hoàn tất xử lý')).toBeInTheDocument()
  await advance(20_000)
  expect(requests).toBe(4)
})

it('VT-018: request chưa trả lời không bị chồng request khác', async () => {
  let requests = 0
  let release!: () => void
  const held = new Promise<void>((resolve) => {
    release = resolve
  })
  server.use(
    http.get('*/api/v1/jobs/:id', async () => {
      requests++
      await held
      return HttpResponse.json({ ...running, status: 'succeeded' })
    }),
  )
  setup()
  await advance(30_000)
  expect(requests).toBe(1)
  await act(async () => release())
  await advance(100)
  expect(screen.getByText('Hoàn tất xử lý')).toBeInTheDocument()
})

it('VT-018: lỗi 404 dừng poll và không hứa sẽ tự kiểm tra lại', async () => {
  let requests = 0
  server.use(
    http.get('*/api/v1/jobs/:id', () =>
      ++requests === 1
        ? HttpResponse.json(running)
        : HttpResponse.json(
            { error: { code: 'NOT_FOUND', message: 'missing' } },
            { status: 404 },
          ),
    ),
  )
  setup()
  await advance(100)
  await advance(2000)
  expect(screen.getByRole('alert')).toHaveTextContent(
    'Đã dừng tự động kiểm tra',
  )
  expect(screen.getByRole('alert')).not.toHaveTextContent(
    'Tự động kiểm tra lại sau',
  )
  await advance(30_000)
  expect(requests).toBe(2)
})
