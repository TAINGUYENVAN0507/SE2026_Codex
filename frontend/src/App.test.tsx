import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  afterAll,
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest'
import { setupServer } from 'msw/node'
import { handlers } from './mocks/handlers'
import { resetMockAuth } from './mocks/auth'
import userMe from '../../contracts/fixtures/api/user_me.json'
import App from './App'

const server = setupServer(...handlers)
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  resetMockAuth()
})
afterAll(() => server.close())

function renderAt(path: string, authenticated = true) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  if (authenticated) client.setQueryData(['me'], userMe)
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
})

describe('meeting workspace', () => {
  it('edits transcript safely and exports the updated content', async () => {
    const user = userEvent.setup()
    renderAt('/meetings/sprint-42')
    await user.click(screen.getByRole('button', { name: 'Sửa đoạn s0' }))
    const field = screen.getByRole('textbox', { name: 'Chỉnh sửa transcript' })
    await user.clear(field)
    await user.click(screen.getByRole('button', { name: /Lưu thay đổi/ }))
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Nội dung không được để trống',
    )
    await user.click(field)
    await user.paste('Nội dung đã sửa <script>không thực thi</script>')
    await user.click(screen.getByRole('button', { name: /Lưu thay đổi/ }))
    expect(
      screen.getByText('Nội dung đã sửa <script>không thực thi</script>'),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Xem bản AI gốc' }))
    expect(
      screen.getByText(/Chào mọi người, hôm nay chúng ta chốt/),
    ).toBeInTheDocument()
  })

  it('adds and completes a task', async () => {
    const user = userEvent.setup()
    renderAt('/meetings/sprint-42')
    const panel = screen.getByRole('complementary')
    await user.click(within(panel).getByRole('button', { name: /Công việc/ }))
    await user.type(
      screen.getByRole('textbox', { name: 'Công việc mới' }),
      'Kiểm tra giao diện',
    )
    await user.click(screen.getByRole('button', { name: 'Thêm công việc' }))
    const done = screen.getByRole('checkbox', {
      name: 'Hoàn thành: Kiểm tra giao diện',
    })
    await user.click(done)
    expect(done).toBeChecked()
    expect(
      screen.getByText('3 việc cần làm · 1 hoàn thành'),
    ).toBeInTheDocument()
  })

  it('finds transcript and can seek from evidence', async () => {
    const user = userEvent.setup()
    renderAt('/meetings/sprint-42')
    await user.type(
      screen.getByRole('textbox', { name: 'Tìm trong transcript' }),
      'OpenAPI',
    )
    expect(screen.getAllByRole('article')).toHaveLength(1)
    await user.clear(
      screen.getByRole('textbox', { name: 'Tìm trong transcript' }),
    )
    const notes = screen.getByRole('complementary')
    await user.click(within(notes).getByRole('button', { name: '10:20' }))
    expect(screen.getByRole('slider', { name: 'Tua bản ghi' })).toHaveValue(
      '620',
    )
  })

  it('updates the player speaker when seeking to another segment', () => {
    renderAt('/meetings/sprint-42')
    const player = screen.getByRole('region', { name: 'Player audio cuộc họp' })
    fireEvent.change(
      within(player).getByRole('slider', { name: 'Tua bản ghi' }),
      {
        target: { value: '620' },
      },
    )
    expect(within(player).getByText('Minh Quang')).toBeInTheDocument()
  })

  it('does not request microphone on page load or switching recording mode', async () => {
    const getUserMedia = vi.fn()
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia },
    })
    const user = userEvent.setup()
    renderAt('/meetings/new')
    await user.click(screen.getByRole('button', { name: 'Ghi âm' }))
    expect(
      screen.getByRole('button', { name: 'Bắt đầu ghi âm' }),
    ).toBeDisabled()
    expect(getUserMedia).not.toHaveBeenCalled()
  })

  it('rejects invalid uploads before creating a meeting', () => {
    renderAt('/meetings/new')
    const input = screen.getByLabelText('Chọn file audio')
    fireEvent.change(input, {
      target: {
        files: [new File(['hello'], 'notes.txt', { type: 'text/plain' })],
      },
    })
    expect(screen.getByRole('alert')).toHaveTextContent('Định dạng chưa hỗ trợ')
    expect(screen.getByRole('button', { name: 'Tạo biên bản' })).toBeDisabled()
  })

  it('logs in through the auth API', async () => {
    const user = userEvent.setup()
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    renderAt('/login')
    await user.type(
      screen.getByRole('textbox', { name: 'Email' }),
      'user@example.com',
    )
    await user.type(
      screen.getByLabelText('Mật khẩu', { selector: 'input' }),
      'demo-password',
    )
    await user.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    expect(
      fetchSpy.mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : String(request)).includes(
          '/auth/login',
        ),
      ),
    ).toBe(true)
    fetchSpy.mockRestore()
  })

  it('redirects a protected route to login and returns after API sign-in', async () => {
    const user = userEvent.setup()
    renderAt('/meetings/new?source=shortcut', false)

    expect(
      await screen.findByRole('heading', { name: 'Chào mừng trở lại' }),
    ).toBeInTheDocument()

    await user.type(
      screen.getByRole('textbox', { name: 'Email' }),
      'user@example.com',
    )
    await user.type(
      screen.getByLabelText('Mật khẩu', { selector: 'input' }),
      'demo-password',
    )
    await user.click(screen.getByRole('button', { name: 'Đăng nhập' }))

    expect(
      await screen.findByRole('heading', { name: 'Tạo cuộc họp mới' }),
    ).toBeInTheDocument()
  })

  it('shows a missing meeting without substituting unrelated demo data', () => {
    renderAt('/meetings/not-a-real-id')
    expect(
      screen.getByRole('heading', { name: 'Không tìm thấy cuộc họp' }),
    ).toBeInTheDocument()
  })
})
