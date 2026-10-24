import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'
import edits from '../../../../contracts/fixtures/api/edits.json'
import { handlers } from '../../mocks/handlers'
import { HistoryPanel } from './HistoryPanel'

const server = setupServer(...handlers)
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
function renderHistory() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  render(
    <QueryClientProvider client={client}>
      <HistoryPanel meetingId={edits.items[0].meeting_id} />
    </QueryClientProvider>,
  )
}

describe('FE-14 edit history', () => {
  it('renders actor, local time, field and before/after from the fixture', async () => {
    renderHistory()
    expect(
      await screen.findByText(edits.items[0].actor.display_name),
    ).toBeInTheDocument()
    expect(screen.getByText(edits.items[0].before)).toBeInTheDocument()
    expect(screen.getByText(edits.items[0].after)).toBeInTheDocument()
    expect(screen.getByText('Transcript · text')).toBeInTheDocument()
    expect(screen.getByText(/16:12/)).toHaveAttribute(
      'dateTime',
      edits.items[0].created_at,
    )
  })

  it('filters by entity type and displays the empty result', async () => {
    renderHistory()
    await screen.findByText(edits.items[0].after)
    await userEvent
      .setup()
      .selectOptions(screen.getByLabelText('Loại thay đổi'), 'speaker')
    expect(
      await screen.findByText('Chưa có chỉnh sửa phù hợp.'),
    ).toBeInTheDocument()
    expect(screen.queryByText(edits.items[0].after)).not.toBeInTheDocument()
  })

  it('requests pages and resets to the first page when filtering', async () => {
    const requests: URL[] = []
    server.use(
      http.get('*/api/v1/meetings/:id/edits', ({ request }) => {
        const url = new URL(request.url)
        requests.push(url)
        const page = Number(url.searchParams.get('page'))
        return HttpResponse.json({
          items: [{ ...edits.items[0], after: `Trang dữ liệu ${page}` }],
          total: 11,
        })
      }),
    )
    renderHistory()
    await screen.findByText('Trang dữ liệu 1')
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Sau' }))
    expect(await screen.findByText('Trang dữ liệu 2')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sau' })).toBeDisabled()
    expect(requests.at(-1)?.searchParams.get('page_size')).toBe('10')
    await user.selectOptions(screen.getByLabelText('Loại thay đổi'), 'summary')
    await screen.findByText('Trang dữ liệu 1')
    expect(requests.at(-1)?.searchParams.get('entity_type')).toBe('summary')
    expect(requests.at(-1)?.searchParams.get('page')).toBe('1')
  })

  it('shows loading until data arrives', async () => {
    let finish!: () => void
    server.use(
      http.get('*/api/v1/meetings/:id/edits', async () => {
        await new Promise<void>((resolve) => {
          finish = resolve
        })
        return HttpResponse.json({ items: [], total: 0 })
      }),
    )
    renderHistory()
    expect(screen.getByRole('status')).toHaveTextContent('Đang tải lịch sử')
    await waitFor(() => expect(finish).toBeTypeOf('function'))
    await act(async () => finish())
    expect(
      await screen.findByText('Chưa có chỉnh sửa phù hợp.'),
    ).toBeInTheDocument()
  })

  it('shows a safe error and can retry', async () => {
    server.use(
      http.get('*/api/v1/meetings/:id/edits', () =>
        HttpResponse.json(
          { error: { code: 'PRIVATE', message: 'CANARY_TRANSCRIPT' } },
          { status: 500 },
        ),
      ),
    )
    renderHistory()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Không tải được lịch sử',
    )
    expect(screen.queryByText(/CANARY_TRANSCRIPT/)).not.toBeInTheDocument()
    server.resetHandlers()
    await userEvent
      .setup()
      .click(screen.getByRole('button', { name: 'Thử lại' }))
    expect(await screen.findByText(edits.items[0].after)).toBeInTheDocument()
  })
})
