import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
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
import { authHandlers, resetMockAuth } from '../mocks/auth'
import { LoginPage } from './LoginPage'

const server = setupServer(...authHandlers)
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  resetMockAuth()
  vi.restoreAllMocks()
})
afterAll(() => server.close())

function renderLogin(next = '/meetings/new') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter
        initialEntries={[`/login?next=${encodeURIComponent(next)}`]}
      >
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/meetings/new" element={<h1>Trang đích</h1>} />
          <Route path="/meetings" element={<h1>Danh sách</h1>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return client
}

async function fill(password = 'demo-password') {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Email'), 'user@example.com')
  await user.type(
    screen.getByLabelText('Mật khẩu', { selector: 'input' }),
    password,
  )
  return user
}

describe('FE-03 API login', () => {
  it('navigates to safe next and never stores credentials', async () => {
    const storage = vi.spyOn(Storage.prototype, 'setItem')
    renderLogin()
    const user = await fill()
    await user.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    expect(
      await screen.findByRole('heading', { name: 'Trang đích' }),
    ).toBeInTheDocument()
    expect(storage).not.toHaveBeenCalled()
  })

  it('keeps email and clears password after 401', async () => {
    renderLogin()
    const user = await fill('wrong-password')
    await user.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Email hoặc mật khẩu không chính xác.',
    )
    expect(screen.getByLabelText('Email')).toHaveValue('user@example.com')
    expect(
      screen.getByLabelText('Mật khẩu', { selector: 'input' }),
    ).toHaveValue('')
  })

  it('shows a separate network error', async () => {
    server.use(http.post('*/api/v1/auth/login', () => HttpResponse.error()))
    renderLogin()
    const user = await fill()
    await user.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Không thể kết nối máy chủ',
    )
  })

  it('disables submission until the response arrives', async () => {
    let finish!: () => void
    server.use(
      http.post('*/api/v1/auth/login', async () => {
        await new Promise<void>((resolve) => {
          finish = resolve
        })
        return HttpResponse.json(
          { error: { code: 'INVALID_CREDENTIALS', message: 'Invalid' } },
          { status: 401 },
        )
      }),
    )
    renderLogin()
    const user = await fill()
    await user.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    expect(
      screen.getByRole('button', { name: 'Đang đăng nhập…' }),
    ).toBeDisabled()
    finish()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })

  it('rejects an external next URL', async () => {
    renderLogin('//example.com')
    const user = await fill()
    await user.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    expect(
      await screen.findByRole('heading', { name: 'Danh sách' }),
    ).toBeInTheDocument()
  })
})
