import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it, vi } from 'vitest'
import meeting from '../../../../contracts/fixtures/api/meeting_processing.json'
import transcript from '../../../../contracts/fixtures/api/transcript_ready.json'
import type { MeetingDetail, TranscriptData } from '../../api/client'
import { handlers } from '../../mocks/handlers'
import { MeetingDetailPage } from '../../pages/MeetingDetailPage'
import { DemoStore } from './DemoStore'
import { apiMeetingToView } from './apiModel'
import { Transcript } from './Transcript'
import { useTranscriptQuery } from './useTranscriptQuery'

const server = setupServer(...handlers)
let client: QueryClient
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(async () => {
  cleanup()
  await client?.cancelQueries()
  client?.clear()
  server.resetHandlers()
  vi.restoreAllMocks()
  vi.useRealTimers()
})
afterAll(() => server.close())
function provider(children: React.ReactNode) {
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}
const empty = { ...transcript, speakers: [], segments: [] }

it('FE-20: trang API ready với 0 segment báo không nhận ra lời nói, không chờ xử lý', async () => {
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
  server.use(
    http.get('*/api/v1/meetings/:id', () =>
      HttpResponse.json({
        ...meeting,
        status: 'ready',
        latest_job: null,
        latest_job_id: null,
        audio: { ...meeting.audio, available: false },
      }),
    ),
    http.get('*/api/v1/meetings/:id/transcript', () =>
      HttpResponse.json(empty),
    ),
  )
  render(
    provider(
      <DemoStore>
        <MemoryRouter initialEntries={[`/meetings/${meeting.id}`]}>
          <Routes>
            <Route
              path="/meetings/:meetingId"
              element={<MeetingDetailPage />}
            />
          </Routes>
        </MemoryRouter>
      </DemoStore>,
    ),
  )
  expect(
    await screen.findByText('Không nhận ra lời nói trong bản ghi'),
  ).toBeVisible()
  expect(
    screen.queryByText('Transcript sẽ xuất hiện khi cuộc họp được xử lý.'),
  ).not.toBeInTheDocument()
  expect(screen.queryByText('Đang tạo transcript…')).not.toBeInTheDocument()
})

it('FE-20: chưa có transcript đã xử lý vẫn giữ thông báo chờ hiện tại', () => {
  render(
    provider(
      <Transcript
        meeting={apiMeetingToView(
          meeting as MeetingDetail,
          empty as TranscriptData,
        )}
        position={0}
        onSeek={() => {}}
        onUpdate={() => {}}
      />,
    ),
  )
  expect(
    screen.getByText('Transcript sẽ xuất hiện khi cuộc họp được xử lý.'),
  ).toBeVisible()
})
function Probe() {
  const query = useTranscriptQuery(meeting.id)
  return <p>{query.data?.status}</p>
}
it.each(['ready', 'pending'] as const)(
  'FE-20: transcript %s với [] có đúng lịch polling',
  async (status) => {
    let requests = 0
    server.use(
      http.get('*/api/v1/meetings/:id/transcript', () => {
        requests++
        return HttpResponse.json({ ...empty, status })
      }),
    )
    vi.useFakeTimers()
    render(provider(<Probe />))
    await act(() => vi.advanceTimersByTimeAsync(100))
    expect(requests).toBe(1)
    if (status === 'ready') {
      for (let second = 0; second < 15; second++)
        await act(() => vi.advanceTimersByTimeAsync(1000))
      expect(requests).toBe(1)
    } else {
      await act(() => vi.advanceTimersByTimeAsync(5000))
      expect(requests).toBe(2)
    }
    expect(screen.getByText(status)).toBeInTheDocument()
  },
)
