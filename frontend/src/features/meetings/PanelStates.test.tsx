import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor, cleanup } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it, vi } from 'vitest'
import { RemoteSummary } from './RemoteSummary'
import { RemoteTasks } from './RemoteTasks'
import { apiMeetingToView } from './apiModel'
import type { MeetingDetail, TranscriptData } from '../../api/client'
import { handlers, resetMockMeetings } from '../../mocks/handlers'
import meeting from '../../../../contracts/fixtures/api/meeting_processing.json'
import transcript from '../../../../contracts/fixtures/api/transcript_ready.json'
import summary from '../../../../contracts/fixtures/api/summary_ready.json'
import tasks from '../../../../contracts/fixtures/api/action_items.json'

const server = setupServer(...handlers)
const view = apiMeetingToView(
  meeting as MeetingDetail,
  transcript as TranscriptData,
)
const clients: QueryClient[] = []
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(async () => {
  cleanup()
  for (const client of clients.splice(0)) {
    await client.cancelQueries()
    client.clear()
  }
  server.resetHandlers()
  resetMockMeetings()
})
afterAll(() => server.close())
function setup(kind: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  clients.push(client)
  render(
    <QueryClientProvider client={client}>
      {kind === 'summary' ? (
        <RemoteSummary meeting={view} onSeek={vi.fn()} />
      ) : (
        <RemoteTasks meeting={view} onSeek={vi.fn()} />
      )}
    </QueryClientProvider>,
  )
}

it.each([
  ['summary', 'summary', 'Đang tải tóm tắt', summary, summary.content.overview],
  [
    'tasks',
    'action-items',
    'Đang tải công việc',
    tasks,
    tasks.items[0].description,
  ],
] as const)(
  '%s: loading remains visible until a successful response',
  async (kind, resource, text, data, readyText) => {
    let release!: () => void
    server.use(
      http.get(`*/api/v1/meetings/:id/${resource}`, async () => {
        await new Promise<void>((resolve) => {
          release = resolve
        })
        return HttpResponse.json(data)
      }),
    )
    setup(kind)
    expect(screen.getByRole('status')).toHaveTextContent(text)
    expect(screen.queryByText(readyText)).not.toBeInTheDocument()
    await waitFor(() => expect(release).toBeTypeOf('function'))
    await act(async () => release())
    expect(await screen.findByText(readyText)).toBeInTheDocument()
  },
)

it.each([
  ['summary', 'summary', 'Không tải được tóm tắt'],
  ['tasks', 'action-items', 'Không tải được công việc'],
])(
  '%s: a transport failure shows an alert without backend content',
  async (kind, resource, text) => {
    server.use(
      http.get(`*/api/v1/meetings/:id/${resource}`, () =>
        HttpResponse.json(
          {
            error: {
              code: 'INTERNAL_ERROR',
              message: 'CANARY_BACKEND_CONTENT',
            },
          },
          { status: 500 },
        ),
      ),
    )
    setup(kind)
    expect(await screen.findByRole('alert')).toHaveTextContent(text)
    expect(screen.queryByText('CANARY_BACKEND_CONTENT')).not.toBeInTheDocument()
  },
)

it('tasks: an empty response shows zero counts and offers manual creation', async () => {
  server.use(
    http.get('*/api/v1/meetings/:id/action-items', () =>
      HttpResponse.json({ ...tasks, items: [] }),
    ),
  )
  setup('tasks')
  expect(
    await screen.findByText('0 việc cần làm · 0 hoàn thành'),
  ).toBeInTheDocument()
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  expect(screen.getByRole('textbox', { name: 'Thêm nội dung' })).toHaveValue('')
  expect(screen.getByRole('button', { name: 'Thêm công việc' })).toBeEnabled()
})
