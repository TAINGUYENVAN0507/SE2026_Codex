import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
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
