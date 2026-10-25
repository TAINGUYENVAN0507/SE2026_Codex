import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
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
import { AppShell } from './AppShell'
import { ConnectivityNotice } from './ConnectivityNotice'
import { toNetworkError } from '../api/errors'
import App from '../App'
import userMe from '../../../contracts/fixtures/api/user_me.json'

const server = setupServer()
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  vi.restoreAllMocks()
  vi.useRealTimers()
})
afterAll(() => server.close())

function renderApp(path: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  client.setQueryData(['me'], userMe)
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('FE-16 resilient routes', () => {
  it('catches a render error without revealing its message and recovers on navigation', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    function Crash(): never {
      throw new Error('CANARY_TRANSCRIPT_PRIVATE_STACK')
    }
    render(
      <MemoryRouter initialEntries={['/crash']}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/crash" element={<Crash />} />
            <Route path="/meetings" element={<h1>Danh sách an toàn</h1>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Trang gặp sự cố')
    expect(screen.getByRole('button', { name: 'Tải lại' })).toBeInTheDocument()
    expect(screen.queryByText(/CANARY_TRANSCRIPT/)).not.toBeInTheDocument()
    await userEvent
      .setup()
      .click(screen.getByRole('link', { name: 'Về danh sách cuộc họp' }))
    expect(
      screen.getByRole('heading', { name: 'Danh sách an toàn' }),
    ).toBeInTheDocument()
  })

  it('shows and hides the offline banner, including an offline initial load', () => {
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
    render(<ConnectivityNotice />)
    expect(screen.getByRole('status')).toHaveTextContent('mất kết nối mạng')
    fireEvent(window, new Event('online'))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    fireEvent(window, new Event('offline'))
    expect(screen.getByRole('status')).toHaveTextContent('mất kết nối mạng')
  })

  it('shows a safe toast for request network failures and dismisses it', () => {
    vi.useFakeTimers()
    render(<ConnectivityNotice />)
    act(() => {
      toNetworkError()
    })
    expect(screen.getByRole('status')).toHaveTextContent(
      'Không thể kết nối máy chủ',
    )
    act(() => {
      vi.advanceTimersByTime(6000)
    })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('renders 404 for an unknown route', () => {
    renderApp('/unknown-route')
    expect(
      screen.getByRole('heading', { name: 'Không tìm thấy trang' }),
    ).toBeInTheDocument()
    expect(screen.getByText('404')).toBeInTheDocument()
  })

  it('renders the meeting 404 for MEETING_NOT_FOUND without leaking the server message', async () => {
    server.use(
      http.get('*/api/v1/meetings/:id', () =>
        HttpResponse.json(
          {
            error: { code: 'MEETING_NOT_FOUND', message: 'CANARY_TRANSCRIPT' },
          },
          { status: 404 },
        ),
      ),
      http.get('*/api/v1/meetings/:id/transcript', () =>
        HttpResponse.json(
          {
            error: { code: 'MEETING_NOT_FOUND', message: 'CANARY_TRANSCRIPT' },
          },
          { status: 404 },
        ),
      ),
    )
    renderApp('/meetings/8f6c2a1e-b2c3-4d4e-8f9a-0b1c2d3e4f5a')
    expect(
      await screen.findByRole('heading', { name: 'Không tìm thấy cuộc họp' }),
    ).toBeInTheDocument()
    expect(screen.getByText('404')).toBeInTheDocument()
    expect(screen.queryByText(/CANARY_TRANSCRIPT/)).not.toBeInTheDocument()
  })
})
