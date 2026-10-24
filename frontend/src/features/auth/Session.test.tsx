import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from 'vitest'
import App from '../../App'
import { handlers } from '../../mocks/handlers'
import { resetMockAuth } from '../../mocks/auth'
import userMe from '../../../../contracts/fixtures/api/user_me.json'

const server = setupServer(...handlers)
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  resetMockAuth()
  vi.restoreAllMocks()
})
afterAll(() => server.close())

function Location() {
  const location = useLocation()
  return (
    <output aria-label="URL">
      {location.pathname + location.search + location.hash}
    </output>
  )
}

function renderSession(path = '/meetings/new', signedIn = false) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  if (signedIn) client.setQueryData(['me'], userMe)
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
        <Location />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return client
}

describe('FE-03 session guard and logout', () => {
  it('shows a skeleton while checking the session, then redirects with the full next URL', async () => {
    let finish!: () => void
    server.use(
      http.get('*/api/v1/auth/me', async () => {
        await new Promise<void>((resolve) => {
          finish = resolve
        })
        return HttpResponse.json(
          { error: { code: 'UNAUTHENTICATED', message: 'Expired' } },
          { status: 401 },
        )
      }),
    )
    renderSession('/meetings/new?source=shortcut#upload')
    expect(
      screen.getByRole('status', { name: 'Đang kiểm tra phiên đăng nhập' }),
    ).toBeInTheDocument()
    await waitFor(() => expect(finish).toBeTypeOf('function'))
    await act(async () => finish())
    expect(
      await screen.findByRole('heading', { name: 'Chào mừng trở lại' }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('URL')).toHaveTextContent(
      '/login?next=%2Fmeetings%2Fnew%3Fsource%3Dshortcut%23upload',
    )
  })

  it('admits a session returned by auth/me', async () => {
    server.use(http.get('*/api/v1/auth/me', () => HttpResponse.json(userMe)))
    renderSession()
    expect(
      await screen.findByRole('heading', { name: 'Tạo cuộc họp mới' }),
    ).toBeInTheDocument()
    expect(screen.getByText(userMe.user.display_name)).toBeInTheDocument()
  })

  it('clears every query on logout and returns to login', async () => {
    const user = userEvent.setup()
    const client = renderSession('/meetings/new', true)
    client.setQueryData(['transcript', 'private'], { text: 'PRIVATE_CANARY' })
    await user.click(screen.getByRole('button', { name: 'Đăng xuất' }))
    expect(
      await screen.findByRole('heading', { name: 'Chào mừng trở lại' }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('URL')).toHaveTextContent('/login')
    expect(client.getQueryCache().getAll()).toHaveLength(0)
  })

  it('ends the session for a 401 from another API, even without an error envelope', async () => {
    server.use(
      http.get(
        '*/api/v1/meetings',
        () => new HttpResponse('Unauthorized', { status: 401 }),
      ),
    )
    const client = renderSession('/meetings?page=2', true)
    expect(
      await screen.findByRole('heading', { name: 'Chào mừng trở lại' }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('URL')).toHaveTextContent(
      '/login?next=%2Fmeetings%3Fpage%3D2',
    )
    expect(client.getQueryData(['me'])).toBeUndefined()
  })

  it('keeps the session when logout fails on the network', async () => {
    server.use(http.post('*/api/v1/auth/logout', () => HttpResponse.error()))
    renderSession('/meetings/new', true)
    await userEvent
      .setup()
      .click(screen.getByRole('button', { name: 'Đăng xuất' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Chưa thể đăng xuất',
    )
    expect(
      screen.getByRole('heading', { name: 'Tạo cuộc họp mới' }),
    ).toBeInTheDocument()
  })
})
