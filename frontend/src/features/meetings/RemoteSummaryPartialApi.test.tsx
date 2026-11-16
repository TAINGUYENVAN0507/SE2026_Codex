import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it, vi } from 'vitest'
import meeting from '../../../../contracts/fixtures/api/meeting_processing.json'
import transcript from '../../../../contracts/fixtures/api/transcript_ready.json'
import {
  getSummary,
  type MeetingDetail,
  type TranscriptData,
} from '../../api/client'
import { handlers, resetMockMeetings } from '../../mocks/handlers'
import { apiMeetingToView } from './apiModel'
import { RemoteSummary } from './RemoteSummary'

// Đổi dữ liệu đầu vào fixture, giữ nguyên handler MSW của ứng dụng để phát hiện drift.
vi.mock(
  '../../../../contracts/fixtures/api/meeting_processing.json',
  async (original) => {
    const fixture = await original<{ default: MeetingDetail }>()
    return { default: { ...fixture.default, status: 'partial' } }
  },
)
const server = setupServer(...handlers)
let client: QueryClient | undefined
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(async () => {
  cleanup()
  await client?.cancelQueries()
  client?.clear()
  server.resetHandlers()
  resetMockMeetings()
})
afterAll(() => server.close())

it('MSW theo #56: meeting partial trả summary failed, không pending/ready', async () => {
  expect(meeting.status).toBe('partial')
  expect(await getSummary(meeting.id)).toMatchObject({
    status: 'failed',
    content: null,
  })
})

it('API failed hiện tạo lại tóm tắt, không cần cờ fallback partial và không có skeleton', async () => {
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  })
  const view = apiMeetingToView(
    meeting as MeetingDetail,
    transcript as TranscriptData,
  )
  render(
    <QueryClientProvider client={client}>
      <RemoteSummary
        meeting={{ ...view, summaryFailed: false }}
        onSeek={() => {}}
      />
    </QueryClientProvider>,
  )
  expect(
    await screen.findByRole('button', { name: 'Tạo lại tóm tắt' }),
  ).toBeVisible()
  expect(screen.getByText('Tạo tóm tắt thất bại.')).toBeVisible()
  expect(screen.queryByLabelText('Đang tạo tóm tắt…')).not.toBeInTheDocument()
  expect(screen.queryByText('Đang tạo tóm tắt…')).not.toBeInTheDocument()
})
