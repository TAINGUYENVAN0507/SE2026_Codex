import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  act,
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
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
import { handlers, resetMockMeetings } from '../mocks/handlers'
import { resetMockAuth } from '../mocks/auth'
import userMe from '../../../contracts/fixtures/api/user_me.json'
import meeting from '../../../contracts/fixtures/api/meeting_processing.json'
import transcript from '../../../contracts/fixtures/api/transcript_ready.json'
import config from '../../../contracts/fixtures/api/config.json'
import list from '../../../contracts/fixtures/api/meeting_list.json'

const server = setupServer(...handlers)
const clients: QueryClient[] = []
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
beforeEach(() =>
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {}),
)
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
afterAll(() => server.close())

function setup(path: string, signedIn = true, session = userMe) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  if (signedIn) client.setQueryData(['me'], session)
  clients.push(client)
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function hold(endpoint: string, data: Record<string, unknown>) {
  let release!: () => void
  server.use(
    http.get(endpoint, async () => {
      await new Promise<void>((resolve) => {
        release = resolve
      })
      return HttpResponse.json(data)
    }),
  )
  return async () => {
    await waitFor(() => expect(release).toBeTypeOf('function'))
    await act(async () => release())
  }
}

const readyMeeting = {
  ...meeting,
  status: 'ready',
  latest_job_id: null,
  latest_job: null,
}
const detailPath = `/meetings/${meeting.id}`
function ready() {
  server.use(
    http.get('*/api/v1/meetings/:id', () => HttpResponse.json(readyMeeting)),
  )
}
function unavailable() {
  return HttpResponse.json(
    {
      error: {
        code: 'SERVICE_UNAVAILABLE',
        message: 'CANARY_BACKEND',
        details: null,
        request_id: null,
      },
    },
    { status: 503 },
  )
}

it('list: no search results explains recovery and clearing restores the meeting', async () => {
  const user = userEvent.setup()
  setup('/meetings')
  await screen.findByText(list.items[0].title)
  await user.type(
    screen.getByRole('textbox', { name: 'Tìm cuộc họp' }),
    'UNMATCHED_SEARCH',
  )
  expect(
    screen.getByRole('heading', { name: 'Không tìm thấy cuộc họp' }),
  ).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Xóa bộ lọc' }))
  expect(screen.getByRole('textbox', { name: 'Tìm cuộc họp' })).toHaveValue('')
  expect(await screen.findByText(list.items[0].title)).toBeInTheDocument()
})

it('detail: loading is announced until the meeting response arrives', async () => {
  const release = hold('*/api/v1/meetings/:id', readyMeeting)
  setup(detailPath)
  expect(
    screen.getByRole('status', { name: 'Đang tải cuộc họp và transcript…' }),
  ).toHaveAttribute('aria-busy', 'true')
  expect(
    screen.queryByRole('region', { name: 'Player audio cuộc họp' }),
  ).not.toBeInTheDocument()
  await release()
  expect(
    await screen.findByRole('heading', { name: meeting.title }),
  ).toBeInTheDocument()
})

it('detail: an empty transcript has a message and no unrelated sample paragraphs', async () => {
  ready()
  server.use(
    http.get('*/api/v1/meetings/:id/transcript', () =>
      HttpResponse.json({ ...transcript, speakers: [], segments: [] }),
    ),
  )
  setup(detailPath)
  expect(
    await screen.findByRole('heading', { name: 'Chưa có transcript' }),
  ).toBeInTheDocument()
  expect(screen.queryByRole('article')).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Cuộc họp' })).toHaveAttribute(
    'href',
    '/meetings',
  )
})

it('detail: a server failure explains the error and the back link recovers to the list', async () => {
  server.use(http.get('*/api/v1/meetings/:id', unavailable))
  setup(detailPath)
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Không tải được cuộc họp',
  )
  expect(screen.queryByText('CANARY_BACKEND')).not.toBeInTheDocument()
  await userEvent
    .setup()
    .click(screen.getByRole('link', { name: 'Về danh sách cuộc họp' }))
  expect(
    await screen.findByRole('heading', { name: 'Cuộc họp' }),
  ).toBeInTheDocument()
})

it('detail: a missing or unauthorized meeting has a real 404 recovery view', async () => {
  server.use(
    http.get('*/api/v1/meetings/:id', () =>
      HttpResponse.json(
        { error: { code: 'MEETING_NOT_FOUND', message: 'Missing' } },
        { status: 404 },
      ),
    ),
  )
  setup(detailPath)
  expect(
    await screen.findByRole('heading', { name: 'Không tìm thấy cuộc họp' }),
  ).toBeInTheDocument()
  expect(
    screen.getByRole('link', { name: 'Về danh sách cuộc họp' }),
  ).toHaveAttribute('href', '/meetings')
  expect(screen.queryByRole('article')).not.toBeInTheDocument()
})

it('progress: announces loading then shows the no-job state without inventing progress', async () => {
  const release = hold('*/api/v1/meetings/:id', readyMeeting)
  setup(`${detailPath}/processing`)
  expect(
    screen.getByRole('status', { name: 'Đang tải tiến độ xử lý…' }),
  ).toBeInTheDocument()
  await release()
  expect(
    await screen.findByText('Cuộc họp chưa có yêu cầu xử lý.'),
  ).toHaveAttribute('role', 'status')
  expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
})

it('upload: the empty form provides a next action and cannot submit without audio', async () => {
  setup('/meetings/new')
  expect(await screen.findByText(/tối đa 200 MB/)).toBeInTheDocument()
  expect(
    screen.getByRole('heading', { name: 'Kéo file audio vào đây' }),
  ).toBeInTheDocument()
  expect(
    screen.getByRole('button', { name: 'Chọn file trên máy' }),
  ).toBeEnabled()
  expect(screen.getByRole('button', { name: 'Tạo biên bản' })).toBeDisabled()
})

it('upload: config loading disables selection and uses the returned limit when ready', async () => {
  const release = hold('*/api/v1/config', {
    ...config,
    max_upload_mb: 1,
    allowed_extensions: ['.wav'],
  })
  setup('/meetings/new')
  expect(screen.getByRole('status', { name: '' })).toHaveTextContent(
    'Đang tải cấu hình upload',
  )
  expect(
    screen.getByRole('button', { name: 'Chọn file trên máy' }),
  ).toBeDisabled()
  await release()
  expect(await screen.findByText(/tối đa 1 MB/)).toBeInTheDocument()
  expect(
    screen.getByRole('button', { name: 'Chọn file trên máy' }),
  ).toBeEnabled()
  expect(screen.getByLabelText('Chọn file audio')).toHaveAttribute(
    'accept',
    '.wav',
  )
})

it('settings: waits for the account rather than showing an empty profile while auth loads', async () => {
  const release = hold('*/api/v1/auth/me', userMe)
  setup('/settings', false)
  expect(
    screen.getByRole('status', { name: 'Đang kiểm tra phiên đăng nhập' }),
  ).toBeInTheDocument()
  expect(
    screen.queryByRole('heading', { name: 'Thông tin tài khoản' }),
  ).not.toBeInTheDocument()
  await release()
  const profile = await screen.findByRole('region', {
    name: 'Thông tin tài khoản',
  })
  expect(within(profile).getByText(userMe.user.email)).toBeInTheDocument()
})

it('settings: a missing display name has a fallback while retaining the real email', async () => {
  setup('/settings', true, {
    ...userMe,
    user: { ...userMe.user, display_name: '' },
  })
  const profile = screen.getByRole('region', { name: 'Thông tin tài khoản' })
  expect(within(profile).getByText('Chưa có tên')).toBeInTheDocument()
  expect(within(profile).getByText(userMe.user.email)).toBeInTheDocument()
})

it('settings: a 503 checking the account can retry and does not pretend the session expired', async () => {
  let calls = 0
  server.use(
    http.get('*/api/v1/auth/me', () =>
      ++calls === 1 ? unavailable() : HttpResponse.json(userMe),
    ),
  )
  setup('/settings', false)
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Không thể kiểm tra phiên đăng nhập',
  )
  expect(
    screen.queryByRole('heading', { name: 'Chào mừng trở lại' }),
  ).not.toBeInTheDocument()
  await userEvent.setup().click(screen.getByRole('button', { name: 'Thử lại' }))
  const profile = await screen.findByRole('region', {
    name: 'Thông tin tài khoản',
  })
  expect(within(profile).getByText(userMe.user.email)).toBeInTheDocument()
  expect(calls).toBe(2)
})
