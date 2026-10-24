import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from 'vitest'
import meetingFixture from '../../../../contracts/fixtures/api/meeting_processing.json'
import transcriptFixture from '../../../../contracts/fixtures/api/transcript_ready.json'
import ready from '../../../../contracts/fixtures/api/summary_ready.json'
import disabled from '../../../../contracts/fixtures/api/summary_disabled.json'
import {
  getSummary,
  type MeetingDetail,
  type TranscriptData,
} from '../../api/client'
import { handlers, resetMockMeetings } from '../../mocks/handlers'
import { apiMeetingToView } from './apiModel'
import { RemoteSummary } from './RemoteSummary'

const server = setupServer(...handlers)
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  resetMockMeetings()
})
afterAll(() => server.close())

function renderSummary(onSeek = vi.fn()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const meeting = apiMeetingToView(
    meetingFixture as MeetingDetail,
    transcriptFixture as TranscriptData,
  )
  render(
    <QueryClientProvider client={client}>
      <RemoteSummary meeting={meeting} onSeek={onSeek} />
    </QueryClientProvider>,
  )
  return onSeek
}

describe('FE-12 summary API', () => {
  it.each([
    ['pending', 'Đang tạo tóm tắt'],
    ['failed', 'Tạo tóm tắt thất bại'],
    ['insufficient_content', 'chưa đủ'],
    ['disabled', 'chưa được bật'],
  ])('shows the %s state', async (status, text) => {
    server.use(
      http.get('*/api/v1/meetings/:meetingId/summary', () =>
        HttpResponse.json({ ...disabled, status }),
      ),
    )
    renderSummary()
    expect(await screen.findByText(new RegExp(text))).toBeInTheDocument()
    if (status === 'failed')
      expect(
        screen.getByRole('button', { name: 'Tạo lại tóm tắt' }),
      ).toBeInTheDocument()
  })

  it('seeks to evidence and sends the edited overview, points and decisions with version', async () => {
    const user = userEvent.setup()
    const onSeek = renderSummary()
    await screen.findByText(ready.content.overview)
    await user.click(
      screen.getAllByRole('button', { name: /Nghe bằng chứng từ/ })[0],
    )
    expect(onSeek).toHaveBeenCalledWith(transcriptFixture.segments[0].start_sec)
    await user.click(screen.getByRole('button', { name: 'Chỉnh sửa' }))
    await user.clear(
      screen.getByRole('textbox', { name: 'Chỉnh sửa tổng quan' }),
    )
    await user.type(
      screen.getByRole('textbox', { name: 'Chỉnh sửa tổng quan' }),
      'Tổng quan mới',
    )
    await user.click(screen.getByRole('button', { name: 'Thêm ý chính' }))
    await user.type(
      screen.getByRole('textbox', { name: 'Ý chính 2' }),
      'Ý bổ sung',
    )
    await user.click(screen.getByRole('button', { name: 'Xóa decisions 1' }))
    await user.click(screen.getByRole('button', { name: 'Lưu' }))
    expect(await screen.findByText('Tổng quan mới')).toBeInTheDocument()
    expect(screen.getByText('Ý bổ sung')).toBeInTheDocument()
    expect(
      screen.queryByText(ready.content.decisions[0].text),
    ).not.toBeInTheDocument()
    const reloaded = await getSummary(meetingFixture.id)
    expect(reloaded).toMatchObject({
      version: ready.version + 1,
      content: {
        overview: 'Tổng quan mới',
        key_points: [
          expect.objectContaining({ text: ready.content.key_points[0].text }),
          expect.objectContaining({ text: 'Ý bổ sung' }),
        ],
        decisions: [],
      },
    })
  })

  it('keeps the draft on 409', async () => {
    server.use(
      http.put('*/api/v1/meetings/:meetingId/summary', () =>
        HttpResponse.json(
          { error: { code: 'VERSION_CONFLICT', message: 'Conflict' } },
          { status: 409 },
        ),
      ),
    )
    const user = userEvent.setup()
    renderSummary()
    await screen.findByText(ready.content.overview)
    await user.click(screen.getByRole('button', { name: 'Chỉnh sửa' }))
    const field = screen.getByRole('textbox', { name: 'Chỉnh sửa tổng quan' })
    await user.clear(field)
    await user.type(field, 'Bản nháp')
    await user.click(screen.getByRole('button', { name: 'Lưu' }))
    expect(await screen.findByRole('alertdialog')).toHaveTextContent('thay đổi')
    expect(field).toHaveValue('Bản nháp')
  })
})
