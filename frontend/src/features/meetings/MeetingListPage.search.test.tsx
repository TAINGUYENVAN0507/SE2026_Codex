import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it, vi } from 'vitest'
import fixture from '../../../../contracts/fixtures/api/meeting_list.json'
import userMe from '../../../../contracts/fixtures/api/user_me.json'
import { MeetingListPage } from '../../pages/MeetingListPage'
import { DemoStore } from './DemoStore'

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

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  })
  client.setQueryData(['me'], userMe)
  clients.push(client)
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
const item = { ...fixture.items[0], status: 'ready' as const }
function list(items: (typeof item)[], total = items.length) {
  return { items, total, page: 1, page_size: 10 }
}

it.each(['500', 'network'] as const)(
  'FE-04: lỗi %s giữ từ khóa, báo lỗi và tìm lại bằng nút thử lại',
  async (failure) => {
    const q = 'kế hoạch nhóm'
    const requests: string[] = []
    server.use(
      http.get('*/api/v1/meetings', ({ request }) => {
        const search = new URL(request.url).searchParams.get('q')
        if (!search) return HttpResponse.json(list([item]))
        requests.push(search)
        if (requests.length === 1) {
          return failure === 'network'
            ? HttpResponse.error()
            : HttpResponse.json(
                {
                  error: {
                    code: 'INTERNAL_ERROR',
                    message: 'Lỗi tổng hợp',
                    details: null,
                    request_id: null,
                  },
                },
                { status: 500 },
              )
        }
        return HttpResponse.json(list([{ ...item, title: q }]))
      }),
    )
    renderPage()
    await screen.findByText(item.title)
    const input = screen.getByRole('textbox', { name: 'Tìm cuộc họp' })
    fireEvent.change(input, { target: { value: q } })
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Không tải được cuộc họp',
    )
    expect(input).toHaveValue(q)
    expect(
      screen.queryByRole('heading', { name: 'Không tìm thấy cuộc họp' }),
    ).not.toBeInTheDocument()
    expect(requests).toEqual([q])
    await userEvent.click(screen.getByRole('button', { name: 'Thử lại' }))
    expect(await screen.findByText(q)).toBeVisible()
    expect(input).toHaveValue(q)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByText('Hiển thị 1 trên 1 cuộc họp')).toBeVisible()
    expect(requests).toEqual([q, q])
  },
)

it('FE-04: phản hồi a về trễ 1 giây không ghi đè kết quả ab mới hơn', async () => {
  const requests: string[] = []
  const responses: string[] = []
  server.use(
    http.get('*/api/v1/meetings', async ({ request }) => {
      const q = new URL(request.url).searchParams.get('q')
      if (!q) return HttpResponse.json(list([item]))
      requests.push(q)
      if (q === 'a') {
        await new Promise<void>((resolve) => setTimeout(resolve, 1000))
        responses.push(q)
        return HttpResponse.json(
          list([
            { ...item, title: 'Kết quả cũ a' },
            {
              ...item,
              id: '00000000-0000-4000-8000-000000000002',
              title: 'Kết quả cũ a thứ hai',
            },
          ]),
        )
      }
      responses.push(q)
      return HttpResponse.json(list([{ ...item, title: 'Kết quả mới ab' }]))
    }),
  )
  vi.useFakeTimers()
  const view = renderPage()
  await act(() => vi.advanceTimersByTimeAsync(100))
  expect(screen.getByText(item.title)).toBeVisible()
  const input = screen.getByRole('textbox', { name: 'Tìm cuộc họp' })
  fireEvent.change(input, { target: { value: 'a' } })
  await act(() => vi.advanceTimersByTimeAsync(300))
  expect(requests).toEqual(['a'])
  fireEvent.change(input, { target: { value: 'ab' } })
  await act(() => vi.advanceTimersByTimeAsync(300))
  await act(() => vi.advanceTimersByTimeAsync(10))
  expect(requests).toEqual(['a', 'ab'])
  expect(responses).toEqual(['ab'])
  expect(screen.getByText('Kết quả mới ab')).toBeVisible()
  await act(() => vi.advanceTimersByTimeAsync(1000))
  expect(responses).toEqual(['ab', 'a'])
  expect(screen.getByText('Kết quả mới ab')).toBeVisible()
  expect(screen.queryByText('Kết quả cũ a')).not.toBeInTheDocument()
  expect(view.container.querySelectorAll('.meeting-row')).toHaveLength(1)
  expect(screen.getByText('Hiển thị 1 trên 1 cuộc họp')).toBeVisible()
  expect(input).toHaveValue('ab')
})

it('FE-04: đổi trạng thái từ trang 2 về trang 1 và giữ từ khóa tìm', async () => {
  const items = Array.from({ length: 12 }, (_, index) => ({
    ...item,
    id: `00000000-0000-4000-8000-${String(index + 1).padStart(12, '0')}`,
    title: `nhóm ${index + 1}`,
    status: index < 7 ? 'ready' : 'failed',
  }))
  const requests: URL[] = []
  server.use(
    http.get('*/api/v1/meetings', ({ request }) => {
      const url = new URL(request.url)
      requests.push(url)
      const q = url.searchParams.get('q') || ''
      const status = url.searchParams.get('status')
      const page = Number(url.searchParams.get('page') || 1)
      const matched = items.filter(
        (meeting) =>
          meeting.title.includes(q) && (!status || meeting.status === status),
      )
      return HttpResponse.json({
        items: matched.slice((page - 1) * 10, page * 10),
        total: matched.length,
        page,
        page_size: 10,
      })
    }),
  )
  const view = renderPage()
  await screen.findByText('nhóm 1')
  const input = screen.getByRole('textbox', { name: 'Tìm cuộc họp' })
  fireEvent.change(input, { target: { value: 'nhóm' } })
  await waitFor(() =>
    expect(requests.at(-1)?.searchParams.get('q')).toBe('nhóm'),
  )
  await userEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
  expect(await screen.findByText('nhóm 12')).toBeVisible()
  expect(view.container.querySelectorAll('.meeting-row')).toHaveLength(2)
  expect(screen.getByText('Hiển thị 2 trên 12 cuộc họp')).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: /^Hoàn thành/ }))
  expect(await screen.findByText('Hiển thị 7 trên 7 cuộc họp')).toBeVisible()
  expect(view.container.querySelectorAll('.meeting-row')).toHaveLength(7)
  expect(screen.getByText('nhóm 1')).toBeVisible()
  expect(screen.queryByText('nhóm 12')).not.toBeInTheDocument()
  expect(input).toHaveValue('nhóm')
  expect(requests.at(-1)?.searchParams.get('page')).toBe('1')
  expect(requests.at(-1)?.searchParams.get('status')).toBe('ready')
  expect(requests.at(-1)?.searchParams.get('q')).toBe('nhóm')
})

it('FE-04: dán 250 ký tự chỉ gửi 200 ký tự và danh sách vẫn hiện', async () => {
  const queries: string[] = []
  server.use(
    http.get('*/api/v1/meetings', ({ request }) => {
      const q = new URL(request.url).searchParams.get('q')
      if (q) queries.push(q)
      if (q && q.length > 200)
        return HttpResponse.json(
          {
            error: {
              code: 'VALIDATION_ERROR',
              message: 'Từ khóa quá dài',
              details: null,
              request_id: null,
            },
          },
          { status: 422 },
        )
      return HttpResponse.json(list([item]))
    }),
  )
  const user = userEvent.setup()
  renderPage()
  await screen.findByText(item.title)
  const input = screen.getByRole('textbox', { name: 'Tìm cuộc họp' })
  await user.click(input)
  await user.paste('x'.repeat(250))
  await waitFor(() => expect(queries.length).toBeGreaterThan(0))
  expect(queries).toEqual(['x'.repeat(200)])
  expect(input).toHaveValue('x'.repeat(200))
  expect(input).toHaveAttribute('maxlength', '200')
  expect(await screen.findByText('Hiển thị 1 trên 1 cuộc họp')).toBeVisible()
  expect(screen.getByText(item.title)).toBeVisible()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

it.each([
  { initialTotal: 11, remainingTotal: 10, initialPage: 2, lastPage: 1 },
  { initialTotal: 25, remainingTotal: 15, initialPage: 3, lastPage: 2 },
])(
  'FE-04: trang $initialPage rỗng sau poll quay về trang $lastPage',
  async ({ initialTotal, remainingTotal, initialPage, lastPage }) => {
    const items = Array.from({ length: initialTotal }, (_, index) => ({
      ...item,
      id: `00000000-0000-4000-8000-${String(index + 1).padStart(12, '0')}`,
      title: `Cuộc họp ${index + 1}`,
      status: 'processing',
    }))
    const requests: number[] = []
    let currentPageRequests = 0
    let removed = false
    server.use(
      http.get('*/api/v1/meetings', ({ request }) => {
        const page = Number(new URL(request.url).searchParams.get('page'))
        requests.push(page)
        if (page === initialPage) {
          currentPageRequests++
          if (currentPageRequests > 1) removed = true
        }
        const available = items.slice(
          0,
          removed ? remainingTotal : initialTotal,
        )
        return HttpResponse.json({
          items: available.slice((page - 1) * 10, page * 10).map((meeting) => ({
            ...meeting,
            status: removed ? 'ready' : 'processing',
          })),
          total: available.length,
          page,
          page_size: 10,
        })
      }),
    )
    vi.useFakeTimers()
    const view = renderPage()
    await act(() => vi.advanceTimersByTimeAsync(100))
    expect(
      screen.getByText(`Hiển thị 10 trên ${initialTotal} cuộc họp`),
    ).toBeVisible()
    for (let page = 2; page <= initialPage; page++) {
      fireEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
      await act(() => vi.advanceTimersByTimeAsync(100))
    }
    expect(screen.getByText(`Cuộc họp ${initialTotal}`)).toBeVisible()
    await act(() => vi.advanceTimersByTimeAsync(5000))
    await act(() => vi.advanceTimersByTimeAsync(100))
    const expectedCount = remainingTotal - (lastPage - 1) * 10
    expect(currentPageRequests).toBe(2)
    expect(
      screen.getByText(
        `Hiển thị ${expectedCount} trên ${remainingTotal} cuộc họp`,
      ),
    ).toBeVisible()
    expect(view.container.querySelectorAll('.meeting-row')).toHaveLength(
      expectedCount,
    )
    expect(requests).toEqual([
      ...Array.from({ length: initialPage }, (_, index) => index + 1),
      initialPage,
      lastPage,
    ])
    expect(
      screen.queryByRole('heading', { name: 'Chưa có cuộc họp' }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByText(`Hiển thị 0 trên ${remainingTotal} cuộc họp`),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByText(`Cuộc họp ${initialTotal}`),
    ).not.toBeInTheDocument()
  },
)

it('FE-04: bộ lọc rỗng báo không có cuộc họp ở trạng thái này và xóa lọc được', async () => {
  const requests: URL[] = []
  server.use(
    http.get('*/api/v1/meetings', ({ request }) => {
      const url = new URL(request.url)
      requests.push(url)
      return HttpResponse.json(
        list(url.searchParams.get('status') === 'failed' ? [] : [item]),
      )
    }),
  )
  const user = userEvent.setup()
  renderPage()
  await screen.findByText(item.title)
  await user.click(screen.getByRole('button', { name: /Có lỗi/ }))
  expect(
    await screen.findByRole('heading', {
      name: 'Không có cuộc họp ở trạng thái này',
    }),
  ).toBeVisible()
  expect(
    screen.queryByRole('heading', { name: 'Chưa có cuộc họp' }),
  ).not.toBeInTheDocument()
  expect(
    screen.queryByText('Tạo cuộc họp mới để bắt đầu.'),
  ).not.toBeInTheDocument()
  expect(requests.at(-1)?.searchParams.get('status')).toBe('failed')
  await user.click(screen.getByRole('button', { name: 'Xóa bộ lọc' }))
  expect(await screen.findByText(item.title)).toBeVisible()
  expect(screen.getByRole('button', { name: /^Tất cả/ })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  expect(
    screen.queryByRole('heading', {
      name: 'Không có cuộc họp ở trạng thái này',
    }),
  ).not.toBeInTheDocument()
})
