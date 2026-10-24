import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen } from '@testing-library/react'
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
import userMe from '../../../../contracts/fixtures/api/user_me.json'

const server = setupServer()
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
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
    expect(await screen.findByText('Chưa có cuộc họp')).toBeInTheDocument()
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
