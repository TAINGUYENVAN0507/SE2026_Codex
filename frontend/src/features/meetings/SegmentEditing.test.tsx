import { useState } from 'react'
import { fireEvent, render, screen, within } from '@testing-library/react'
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
import {
  getTranscript,
  type MeetingDetail,
  type TranscriptData,
} from '../../api/client'
import { handlers, resetMockMeetings } from '../../mocks/handlers'
import { apiMeetingToView } from './apiModel'
import { Transcript } from './Transcript'

const server = setupServer(...handlers)
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  resetMockMeetings()
})
afterAll(() => server.close())

const first = transcriptFixture.segments[0]
const unknown = transcriptFixture.segments[1]

function Harness() {
  const [meeting, setMeeting] = useState(() =>
    apiMeetingToView(
      meetingFixture as MeetingDetail,
      transcriptFixture as TranscriptData,
    ),
  )
  return (
    <Transcript
      meeting={meeting}
      position={0}
      onSeek={() => {}}
      onUpdate={(transform) => setMeeting((current) => transform(current))}
    />
  )
}

async function openEditor() {
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: `Sửa đoạn ${first.id}` }))
  return {
    user,
    field: screen.getByRole('textbox', { name: 'Chỉnh sửa transcript' }),
  }
}

describe('FE-10 segment editing', () => {
  it('saves text through PATCH and keeps it after an API reload', async () => {
    render(<Harness />)
    const { user, field } = await openEditor()
    await user.clear(field)
    await user.type(field, 'Nội dung đã sửa{Control>}{Enter}{/Control}')
    expect(await screen.findByText('Nội dung đã sửa')).toBeInTheDocument()
    const reloaded = await getTranscript(meetingFixture.id)
    expect(
      reloaded.segments?.find((segment) => segment.id === first.id)?.text,
    ).toBe('Nội dung đã sửa')
  })

  it('keeps the draft and offers reload on version conflict', async () => {
    server.use(
      http.patch('*/api/v1/meetings/:meetingId/segments/:segmentId', () =>
        HttpResponse.json(
          { error: { code: 'VERSION_CONFLICT', message: 'Conflict' } },
          { status: 409 },
        ),
      ),
    )
    render(<Harness />)
    const { user, field } = await openEditor()
    await user.clear(field)
    await user.type(field, 'Chữ cần giữ')
    await user.click(screen.getByRole('button', { name: 'Lưu thay đổi' }))
    expect(await screen.findByRole('alertdialog')).toHaveTextContent('tải lại')
    expect(field).toHaveValue('Chữ cần giữ')
    expect(
      within(document.getElementById(`segment-${first.id}`)!).getByRole(
        'textbox',
      ),
    ).toBeInTheDocument()
  })

  it('rolls back optimistic text after a server error', async () => {
    server.use(
      http.patch('*/api/v1/meetings/:meetingId/segments/:segmentId', () =>
        HttpResponse.json(
          { error: { code: 'UNKNOWN_ERROR', message: 'Server error' } },
          { status: 500 },
        ),
      ),
    )
    render(<Harness />)
    const { user, field } = await openEditor()
    await user.clear(field)
    await user.type(field, 'Không được lưu')
    await user.click(screen.getByRole('button', { name: 'Lưu thay đổi' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Đã xảy ra lỗi')
    expect(field).toHaveValue('Không được lưu')
    await user.click(screen.getByRole('button', { name: 'Hủy' }))
    expect(screen.getByText(first.text)).toBeInTheDocument()
  })

  it('rejects empty and over-5000-character text without a request', async () => {
    const patch = vi.fn(() => HttpResponse.json(first))
    server.use(
      http.patch('*/api/v1/meetings/:meetingId/segments/:segmentId', patch),
    )
    render(<Harness />)
    const { user, field } = await openEditor()
    await user.clear(field)
    await user.click(screen.getByRole('button', { name: 'Lưu thay đổi' }))
    expect(screen.getByRole('alert')).toHaveTextContent('không được để trống')
    fireEvent.change(field, { target: { value: 'a'.repeat(5001) } })
    await user.click(screen.getByRole('button', { name: 'Lưu thay đổi' }))
    expect(screen.getByRole('alert')).toHaveTextContent('quá 5000')
    expect(patch).not.toHaveBeenCalled()
  })

  it('changes speaker, restores unknown, and toggles read-only AI original', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const selector = screen.getByRole('combobox', {
      name: `Người nói đoạn ${unknown.id}`,
    })
    await user.selectOptions(selector, transcriptFixture.speakers[0].id)
    expect(await getTranscript(meetingFixture.id)).toMatchObject({
      segments: expect.arrayContaining([
        expect.objectContaining({
          id: unknown.id,
          speaker_id: transcriptFixture.speakers[0].id,
        }),
      ]),
    })
    await user.click(screen.getByRole('checkbox', { name: 'Bản AI gốc' }))
    expect(
      within(document.getElementById(`segment-${unknown.id}`)!).getByText(
        'Chưa xác định',
      ),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('combobox', { name: `Người nói đoạn ${unknown.id}` }),
    ).not.toBeInTheDocument()
    await user.click(screen.getByRole('checkbox', { name: 'Bản AI gốc' }))
    await user.selectOptions(
      screen.getByRole('combobox', { name: `Người nói đoạn ${unknown.id}` }),
      '',
    )
    const reloaded = await getTranscript(meetingFixture.id)
    expect(
      reloaded.segments?.find((segment) => segment.id === unknown.id)
        ?.speaker_id,
    ).toBeNull()
    await user.click(screen.getByRole('checkbox', { name: 'Bản AI gốc' }))
    expect(screen.getByText(first.ai_text)).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: `Sửa đoạn ${first.id}` }),
    ).not.toBeInTheDocument()
    await user.click(screen.getByRole('checkbox', { name: 'Bản AI gốc' }))
    expect(
      screen.getByRole('button', { name: `Sửa đoạn ${first.id}` }),
    ).toBeInTheDocument()
  })

  it('rolls back a speaker change on 409', async () => {
    server.use(
      http.patch('*/api/v1/meetings/:meetingId/segments/:segmentId', () =>
        HttpResponse.json(
          { error: { code: 'VERSION_CONFLICT', message: 'Conflict' } },
          { status: 409 },
        ),
      ),
    )
    const user = userEvent.setup()
    render(<Harness />)
    const selector = screen.getByRole('combobox', {
      name: `Người nói đoạn ${unknown.id}`,
    })
    await user.selectOptions(selector, transcriptFixture.speakers[0].id)
    expect(await screen.findByRole('alertdialog')).toHaveTextContent('tải lại')
    expect(selector).toHaveValue('')
  })
})
