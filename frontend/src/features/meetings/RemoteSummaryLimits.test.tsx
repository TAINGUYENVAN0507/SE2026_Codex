import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it, vi } from 'vitest'
import ready from '../../../../contracts/fixtures/api/summary_ready.json'
import meetingFixture from '../../../../contracts/fixtures/api/meeting_processing.json'
import transcriptFixture from '../../../../contracts/fixtures/api/transcript_ready.json'
import { apiMeetingToView } from './apiModel'
import { RemoteSummary } from './RemoteSummary'
import type { MeetingDetail, TranscriptData } from '../../api/client'

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
})
afterAll(() => server.close())
function renderSummary() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  })
  clients.push(client)
  render(
    <QueryClientProvider client={client}>
      <RemoteSummary
        meeting={apiMeetingToView(
          meetingFixture as MeetingDetail,
          transcriptFixture as TranscriptData,
        )}
        onSeek={vi.fn()}
      />
    </QueryClientProvider>,
  )
}

it.each([
  { field: 'key_points', label: 'ý chính', input: 'Ý chính' },
  { field: 'decisions', label: 'quyết định', input: 'Quyết định' },
] as const)(
  'FE-12: dừng ở 50 $label, xóa còn 49 thì thêm được',
  async ({ field, label, input }) => {
    server.use(
      http.get('*/api/v1/meetings/:id/summary', () =>
        HttpResponse.json({
          ...ready,
          content: {
            ...ready.content,
            [field]: Array.from({ length: 50 }, (_, i) => ({
              text: `Mục ${i + 1}`,
              evidence_segment_ids: [],
            })),
          },
        }),
      ),
    )
    const user = userEvent.setup()
    renderSummary()
    await user.click(await screen.findByRole('button', { name: 'Chỉnh sửa' }))
    const add = screen.getByRole('button', { name: `Thêm ${label}` })
    expect(add).toBeDisabled()
    expect(
      screen.getByText(new RegExp(`Đã đạt giới hạn 50 ${label}`)),
    ).toBeVisible()
    await user.click(add)
    expect(
      screen.getAllByRole('textbox', { name: new RegExp(`^${input} [0-9]+$`) }),
    ).toHaveLength(50)
    await user.click(screen.getByRole('button', { name: `Xóa ${field} 50` }))
    expect(add).toBeEnabled()
    expect(
      screen.queryByText(new RegExp(`Đã đạt giới hạn 50 ${label}`)),
    ).not.toBeInTheDocument()
    await user.click(add)
    expect(screen.getByRole('textbox', { name: `${input} 50` })).toBeVisible()
    expect(add).toBeDisabled()
    expect(
      screen.getAllByRole('textbox', { name: new RegExp(`^${input} [0-9]+$`) }),
    ).toHaveLength(50)
  },
)
