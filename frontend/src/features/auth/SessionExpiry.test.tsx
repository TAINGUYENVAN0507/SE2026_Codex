import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it, vi } from 'vitest'
import App from '../../App'
import { handlers } from '../../mocks/handlers'
import { resetMockAuth } from '../../mocks/auth'
import userMe from '../../../../contracts/fixtures/api/user_me.json'
import meeting from '../../../../contracts/fixtures/api/meeting_processing.json'

const server = setupServer(...handlers)
const clients: QueryClient[] = []
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(async () => {
  cleanup()
  for (const client of clients.splice(0)) {
    await client.cancelQueries()
    client.clear()
  }
  vi.restoreAllMocks()
  server.resetHandlers()
  resetMockAuth()
})
afterAll(() => server.close())

function Location() {
  const location = useLocation()
  return <output aria-label="URL">{location.pathname + location.search}</output>
}

it.each([
  ['danh sách', '/meetings?page=2', '*/api/v1/meetings'],
  ['chi tiết', `/meetings/${meeting.id}?source=link`, '*/api/v1/meetings/:id'],
  ['upload', '/meetings/new?source=shortcut', '*/api/v1/config'],
  ['tiến độ', `/meetings/${meeting.id}/processing`, '*/api/v1/meetings/:id'],
])(
  'FE-16: 401 tại trang %s về login có thông báo và dọn dữ liệu phiên',
  async (_name, path, endpoint) => {
    server.use(
      http.get(
        endpoint,
        () => new HttpResponse('Unauthorized CANARY_RAW', { status: 401 }),
      ),
    )
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    clients.push(client)
    client.setQueryData(['me'], userMe)
    client.setQueryData(['transcript', 'private'], {
      text: 'CANARY_PRIVATE_CACHE',
    })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[path]}>
          <App />
          <Location />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(
      await screen.findByRole(
        'heading',
        { name: 'Chào mừng trở lại' },
        { timeout: 5_000 },
      ),
    ).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại để tiếp tục.',
    )
    expect(screen.getByLabelText('URL')).toHaveTextContent(
      `/login?next=${encodeURIComponent(path)}`,
    )
    // useMe có thể ghi null từ 401 sau khi cache được dọn; cả hai đều không còn danh tính.
    expect([undefined, null]).toContain(client.getQueryData(['me']))
    expect(client.getQueryData(['transcript', 'private'])).toBeUndefined()
    expect(
      screen.queryByText(/CANARY_RAW|CANARY_PRIVATE_CACHE/),
    ).not.toBeInTheDocument()
  },
)

it('FE-16: hai API cùng trả 401 chỉ kết thúc phiên một lần', async () => {
  let release!: () => void
  const pending = new Promise<void>((resolve) => {
    release = resolve
  })
  let requests = 0
  const expired = async () => {
    requests++
    await pending
    return new HttpResponse('Unauthorized CANARY_RAW', { status: 401 })
  }
  server.use(
    http.get('*/api/v1/meetings/:id', expired),
    http.get('*/api/v1/meetings/:id/transcript', expired),
  )
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  clients.push(client)
  client.setQueryData(['me'], userMe)
  client.setQueryData(['transcript', 'private'], {
    text: 'CANARY_PRIVATE_CACHE',
  })
  const clear = vi.spyOn(client, 'clear')
  const path = `/meetings/${meeting.id}?source=concurrent`
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
        <Location />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  await waitFor(() => expect(requests).toBe(2))
  await act(async () => release())
  expect(
    await screen.findByRole('heading', { name: 'Chào mừng trở lại' }),
  ).toBeInTheDocument()
  expect(screen.getByRole('alert')).toHaveTextContent(
    'Phiên đăng nhập đã hết hạn.',
  )
  expect(screen.getByLabelText('URL')).toHaveTextContent(
    `/login?next=${encodeURIComponent(path)}`,
  )
  expect(clear).toHaveBeenCalledTimes(1)
  expect(requests).toBe(2)
  // useMe có thể ghi null từ 401 sau khi cache được dọn; cả hai đều không còn danh tính.
  expect([undefined, null]).toContain(client.getQueryData(['me']))
  expect(client.getQueryData(['transcript', 'private'])).toBeUndefined()
})
