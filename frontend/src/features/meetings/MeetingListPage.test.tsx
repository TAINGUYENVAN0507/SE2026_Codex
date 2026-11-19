import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter } from 'react-router-dom'
import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from 'vitest'
import fixture from '../../../../contracts/fixtures/api/meeting_list.json'
import { MeetingListPage } from '../../pages/MeetingListPage'
import { DemoStore } from './DemoStore'
import { handlers, resetMockMeetings } from '../../mocks/handlers'
import userMe from '../../../../contracts/fixtures/api/user_me.json'

const server = setupServer()
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  server.events.removeAllListeners()
  resetMockMeetings()
  vi.useRealTimers()
})
afterAll(() => server.close())

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  client.setQueryData(['me'], userMe)
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <DemoStore>
          <MeetingListPage />
        </DemoStore>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('FE-04 meeting list', () => {
  it('shows loading, then fixture data', async () => {
    let resolve!: (response: Response) => void
    server.use(
      http.get(
        '*/api/v1/meetings',
        () =>
          new Promise<Response>((done) => {
            resolve = done
          }),
      ),
    )
    renderPage()
    expect(screen.getByRole('status')).toHaveTextContent('Đang tải')
    await vi.waitFor(() => expect(resolve).toBeTypeOf('function'))
    await act(async () => resolve(HttpResponse.json(fixture)))
    expect(await screen.findByText(fixture.items[0].title)).toBeInTheDocument()
  })

  it('shows empty and error states', async () => {
    server.use(
      http.get('*/api/v1/meetings', () =>
        HttpResponse.json({ items: [], page: 1, page_size: 10, total: 0 }),
      ),
    )
    const first = renderPage()
    expect(await screen.findByText('Chưa có cuộc họp')).toBeInTheDocument()
    first.unmount()
    server.use(
      http.get('*/api/v1/meetings', () =>
        HttpResponse.json(
          {
            error: {
              code: 'NETWORK_ERROR',
              message: 'Lỗi',
              details: null,
              request_id: null,
            },
          },
          { status: 503 },
        ),
      ),
    )
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Không tải được cuộc họp',
    )
  })

  it('filters by status from the API', async () => {
    const statuses: string[] = []
    server.use(
      http.get('*/api/v1/meetings', ({ request }) => {
        const status = new URL(request.url).searchParams.get('status') || 'all'
        statuses.push(status)
        return HttpResponse.json({
          ...fixture,
          items: status === 'failed' ? [] : fixture.items,
        })
      }),
    )
    renderPage()
    await screen.findByText(fixture.items[0].title)
    await userEvent.click(screen.getByRole('button', { name: /Có lỗi/ }))
    expect(
      await screen.findByText('Không có cuộc họp ở trạng thái này'),
    ).toBeInTheDocument()
    expect(statuses).toContain('failed')
  })

  it('polls while processing and stops after ready', async () => {
    let requests = 0
    server.use(
      http.get('*/api/v1/meetings', () => {
        requests += 1
        const items =
          requests === 1
            ? fixture.items
            : [{ ...fixture.items[0], status: 'ready' }]
        return HttpResponse.json({ ...fixture, items })
      }),
    )
    vi.useFakeTimers({ shouldAdvanceTime: true })
    renderPage()
    await act(async () => {
      await vi.waitFor(() => expect(requests).toBe(1))
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000)
    })
    expect(requests).toBe(2)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000)
    })
    expect(requests).toBe(2)
  })
})

it('FE-04: tìm cuộc họp thứ 11 qua API, đổi từ trang 2 về trang 1 và trim q', async () => {
  server.use(...handlers)
  for (let index = 0; index < 10; index++) {
    const body = new FormData()
    body.set('title', `Cuộc họp mới ${index}`)
    const result = await fetch('http://localhost/api/v1/meetings', {
      method: 'POST',
      body,
    })
    expect(result.status).toBe(201)
  }
  const requests: URL[] = []
  server.events.on('request:start', ({ request }) => {
    if (
      request.method === 'GET' &&
      new URL(request.url).pathname === '/api/v1/meetings'
    )
      requests.push(new URL(request.url))
  })
  const view = renderPage()
  await screen.findByText('Cuộc họp mới 0')
  expect(view.container.querySelectorAll('.meeting-row')).toHaveLength(10)
  expect(screen.queryByText(fixture.items[0].title)).not.toBeInTheDocument()
  fireEvent.change(screen.getByRole('textbox', { name: 'Tìm cuộc họp' }), {
    target: { value: `  ${fixture.items[0].title}  ` },
  })
  await screen.findByText(fixture.items[0].title)
  expect(view.container.querySelectorAll('.meeting-row')).toHaveLength(1)
  expect(screen.getByText('Hiển thị 1 trên 1 cuộc họp')).toBeInTheDocument()
  expect(
    requests.some(
      (url) => url.searchParams.get('q') === fixture.items[0].title,
    ),
  ).toBe(true)

  fireEvent.change(screen.getByRole('textbox', { name: 'Tìm cuộc họp' }), {
    target: { value: '' },
  })
  await screen.findByText('Cuộc họp mới 0')
  await userEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
  await screen.findByText('Trang 2')
  await screen.findByText(fixture.items[0].title)
  fireEvent.change(screen.getByRole('textbox', { name: 'Tìm cuộc họp' }), {
    target: { value: fixture.items[0].title },
  })
  await waitFor(() =>
    expect(screen.getByText('Hiển thị 1 trên 1 cuộc họp')).toBeInTheDocument(),
  )
  expect(requests.at(-1)?.searchParams.get('page')).toBe('1')
  expect(requests.at(-1)?.searchParams.get('q')).toBe(fixture.items[0].title)
})

it('FE-04: debounce 300 ms gộp từ khóa và hủy lịch gửi trước', async () => {
  const requests: URL[] = []
  server.use(
    http.get('*/api/v1/meetings', ({ request }) => {
      requests.push(new URL(request.url))
      return HttpResponse.json({
        ...fixture,
        items: [{ ...fixture.items[0], status: 'ready' }],
      })
    }),
  )
  vi.useFakeTimers()
  renderPage()
  await act(() => vi.advanceTimersByTimeAsync(100))
  expect(requests).toHaveLength(1)
  fireEvent.change(screen.getByRole('textbox', { name: 'Tìm cuộc họp' }), {
    target: { value: 'cũ' },
  })
  await act(() => vi.advanceTimersByTimeAsync(299))
  expect(requests).toHaveLength(1)
  fireEvent.change(screen.getByRole('textbox', { name: 'Tìm cuộc họp' }), {
    target: { value: '  từ khóa mới  ' },
  })
  await act(() => vi.advanceTimersByTimeAsync(299))
  expect(requests).toHaveLength(1)
  await act(() => vi.advanceTimersByTimeAsync(1))
  expect(requests).toHaveLength(2)
  expect(requests[1].searchParams.get('q')).toBe('từ khóa mới')
})
