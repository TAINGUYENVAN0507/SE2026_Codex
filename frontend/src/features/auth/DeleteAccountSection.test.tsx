import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { beforeAll, afterAll, afterEach, expect, it } from 'vitest'
import { DemoStore } from '../meetings/DemoStore'
import { DeleteAccountSection } from './DeleteAccountSection'

const server = setupServer()
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
})
afterAll(() => server.close())
const email = 'synthetic-user@example.com'
function setup(available = true) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  })
  client.setQueryData(['me'], { user: { id: 'synthetic', email } })
  client.setQueryData(['meeting', 'synthetic'], { private: 'synthetic' })
  render(
    <QueryClientProvider client={client}>
      <DemoStore>
        <MemoryRouter initialEntries={['/settings']}>
          <Routes>
            <Route
              path="/settings"
              element={
                <DeleteAccountSection email={email} available={available} />
              }
            />
            <Route path="/login" element={<h1>Đăng nhập</h1>} />
          </Routes>
        </MemoryRouter>
      </DemoStore>
    </QueryClientProvider>,
  )
  return client
}
it('keeps deletion unavailable until the backend contract supports it', () => {
  setup(false)
  expect(screen.getByRole('button', { name: 'Xóa tài khoản' })).toBeDisabled()
  expect(screen.getByRole('status')).toHaveTextContent('hiện chưa khả dụng')
})
it('requires the email, supports cancel/Escape and clears all cached data only after success', async () => {
  let calls = 0
  server.use(
    http.delete('*/api/v1/auth/me', ({ request }) => {
      expect(request.credentials).toBe('include')
      calls++
      return new HttpResponse(null, { status: 204 })
    }),
  )
  const client = setup()
  const user = userEvent.setup()
  const trigger = screen.getByRole('button', {
    name: 'Xóa tài khoản',
  })
  await user.click(trigger)
  const dialog = screen.getByRole('alertdialog')
  expect(dialog).toHaveTextContent('Mọi cuộc họp và dữ liệu liên quan')
  const field = within(dialog).getByRole('textbox')
  expect(field).toHaveFocus()
  await user.type(field, 'wrong@example.com')
  expect(
    within(dialog).getByRole('button', { name: 'Xóa tài khoản vĩnh viễn' }),
  ).toBeDisabled()
  await user.keyboard('{Escape}')
  expect(trigger).toHaveFocus()
  expect(calls).toBe(0)
  expect(client.getQueryData(['meeting', 'synthetic'])).toBeTruthy()
  await user.click(trigger)
  await user.click(screen.getByRole('button', { name: 'Giữ tài khoản' }))
  expect(calls).toBe(0)
  await user.click(trigger)
  await user.type(screen.getByRole('textbox'), email)
  await user.click(
    screen.getByRole('button', { name: 'Xóa tài khoản vĩnh viễn' }),
  )
  await screen.findByRole('heading', { name: 'Đăng nhập' })
  expect(calls).toBe(1)
  expect(client.getQueryCache().getAll()).toHaveLength(0)
})
it.each([0, 500, 503, 405])(
  'preserves the dialog, email and cache on failure %s',
  async (status) => {
    server.use(
      http.delete('*/api/v1/auth/me', () =>
        status ? new HttpResponse(null, { status }) : HttpResponse.error(),
      ),
    )
    const client = setup()
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Xóa tài khoản' }))
    await user.type(screen.getByRole('textbox'), email)
    await user.click(
      screen.getByRole('button', { name: 'Xóa tài khoản vĩnh viễn' }),
    )
    expect(await screen.findByRole('alert')).toHaveTextContent(
      status === 405 ? 'chưa khả dụng' : 'Chưa thể xóa tài khoản',
    )
    expect(screen.getByRole('alertdialog')).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toHaveValue(email)
    expect(client.getQueryData(['meeting', 'synthetic'])).toBeTruthy()
    expect(
      screen.queryByRole('heading', { name: 'Đăng nhập' }),
    ).not.toBeInTheDocument()
  },
)
it('sends only one request and prevents closing while deletion is in flight', async () => {
  let calls = 0
  let finish: () => void = () => {}
  server.use(
    http.delete('*/api/v1/auth/me', async () => {
      calls++
      await new Promise<void>((resolve) => {
        finish = resolve
      })
      return new HttpResponse(null, { status: 204 })
    }),
  )
  setup()
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Xóa tài khoản' }))
  await user.type(screen.getByRole('textbox'), email)
  await user.dblClick(
    screen.getByRole('button', { name: 'Xóa tài khoản vĩnh viễn' }),
  )
  await user.keyboard('{Escape}')
  expect(screen.getByRole('alertdialog')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Giữ tài khoản' })).toBeDisabled()
  expect(calls).toBe(1)
  finish()
  await screen.findByRole('heading', { name: 'Đăng nhập' })
})
