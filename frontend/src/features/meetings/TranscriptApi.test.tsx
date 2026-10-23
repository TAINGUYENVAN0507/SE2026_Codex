import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { setupServer } from 'msw/node'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from 'vitest'
import meeting from '../../../../contracts/fixtures/api/meeting_processing.json'
import transcriptReady from '../../../../contracts/fixtures/api/transcript_ready.json'
import transcriptPending from '../../../../contracts/fixtures/api/transcript_pending.json'
import { handlers } from '../../mocks/handlers'
import type { MeetingDetail, TranscriptData } from '../../api/client'
import { MeetingDetailPage } from '../../pages/MeetingDetailPage'
import { DemoStore } from './DemoStore'
import { apiMeetingToView } from './apiModel'
import { Transcript } from './Transcript'
import {
  formatTranscriptTime,
  groupConsecutiveSegments,
} from './transcriptUtils'

const server = setupServer(...handlers)
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('FE-09 transcript from API', () => {
  it('renders two speakers, unknown segment, flags and hh:mm:ss timestamps', () => {
    const view = apiMeetingToView(
      meeting as MeetingDetail,
      transcriptReady as TranscriptData,
    )
    render(
      <Transcript
        meeting={view}
        position={0}
        onSeek={vi.fn()}
        onUpdate={vi.fn()}
      />,
    )
    expect(screen.getAllByText('Chị Lan (PM)').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Anh Minh').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Chưa xác định').length).toBeGreaterThan(0)
    expect(screen.getByText('Cần nghe lại')).toBeInTheDocument()
    expect(screen.getByText('Nói chồng')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Nghe từ 00:00:06' }),
    ).toBeInTheDocument()
    expect(formatTranscriptTime(3661.9)).toBe('01:01:01')
  })

  it('groups only adjacent segments of the same speaker', () => {
    const segments = apiMeetingToView(
      meeting as MeetingDetail,
      transcriptReady as TranscriptData,
    ).segments
    expect(
      groupConsecutiveSegments([
        segments[0],
        { ...segments[1], speakerId: segments[0].speakerId },
        segments[2],
      ]).map((group) => group.length),
    ).toEqual([2, 1])
  })

  it('shows a pending skeleton', () => {
    const view = apiMeetingToView(
      meeting as MeetingDetail,
      transcriptPending as TranscriptData,
    )
    render(
      <Transcript
        meeting={view}
        pending
        position={0}
        onSeek={vi.fn()}
        onUpdate={vi.fn()}
      />,
    )
    expect(screen.getByRole('status')).toHaveTextContent('Đang tạo transcript')
  })

  it('loads meeting and transcript through the API client', async () => {
    vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    render(
      <QueryClientProvider client={client}>
        <DemoStore>
          <MemoryRouter initialEntries={[`/meetings/${meeting.id}`]}>
            <Routes>
              <Route
                path="/meetings/:meetingId"
                element={<MeetingDetailPage />}
              />
            </Routes>
          </MemoryRouter>
        </DemoStore>
      </QueryClientProvider>,
    )
    expect((await screen.findAllByText('Chị Lan (PM)')).length).toBeGreaterThan(
      0,
    )
  })
})
