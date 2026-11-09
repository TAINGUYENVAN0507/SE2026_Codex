import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest'
import App from '../../App'
import { handlers } from '../../mocks/handlers'
import { resetMockAuth } from '../../mocks/auth'
import userMe from '../../../../contracts/fixtures/api/user_me.json'
import meeting from '../../../../contracts/fixtures/api/meeting_processing.json'

const server = setupServer(...handlers)
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
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
      await screen.findByRole('heading', { name: 'Chào mừng trở lại' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại để tiếp tục.',
    )
    expect(screen.getByLabelText('URL')).toHaveTextContent(
      `/login?next=${encodeURIComponent(path)}`,
    )
    expect(client.getQueryData(['me'])).toBeUndefined()
    expect(client.getQueryData(['transcript', 'private'])).toBeUndefined()
    expect(
      screen.queryByText(/CANARY_RAW|CANARY_PRIVATE_CACHE/),
    ).not.toBeInTheDocument()
  },
)
