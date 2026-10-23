import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'
import meetingFixture from '../../../../contracts/fixtures/api/meeting_processing.json'
import transcriptFixture from '../../../../contracts/fixtures/api/transcript_ready.json'
import type { MeetingDetail, TranscriptData } from '../../api/client'
import { handlers } from '../../mocks/handlers'
import { apiMeetingToView } from './apiModel'
import { Transcript } from './Transcript'

const server = setupServer(...handlers)
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

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

async function editName(name: string) {
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Đổi tên Chị Lan (PM)' }))
  const field = screen.getByRole('textbox', {
    name: 'Tên mới của Chị Lan (PM)',
  })
  await user.clear(field)
  if (name) await user.type(field, name)
  await user.click(screen.getByRole('button', { name: 'Lưu' }))
  return field
}

describe('FE-11 rename speaker', () => {
  it('updates the name in all segments after API success', async () => {
    render(<Harness />)
    await editName('Lan mới')
    expect((await screen.findAllByText('Lan mới')).length).toBeGreaterThan(1)
  })

  it('rejects blank names locally', async () => {
    render(<Harness />)
    await editName('')
    expect(screen.getByRole('alert')).toHaveTextContent('1 đến 50 ký tự')
  })

  it('shows duplicate-name error beside the input', async () => {
    render(<Harness />)
    await editName('Anh Minh')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'đã được sử dụng',
    )
    expect(
      screen.getByRole('textbox', { name: 'Tên mới của Chị Lan (PM)' }),
    ).toHaveValue('Anh Minh')
  })

  it('offers reload on 409 without discarding the draft', async () => {
    server.use(
      http.patch('*/api/v1/meetings/:meetingId/speakers/:speakerId', () =>
        HttpResponse.json(
          {
            error: {
              code: 'VERSION_CONFLICT',
              message: 'Conflict',
              details: null,
              request_id: null,
            },
          },
          { status: 409 },
        ),
      ),
    )
    render(<Harness />)
    await editName('Lan mới')
    expect(await screen.findByRole('alertdialog')).toHaveTextContent(
      'tải lại trang',
    )
    expect(
      screen.getByRole('textbox', { name: 'Tên mới của Chị Lan (PM)' }),
    ).toHaveValue('Lan mới')
  })
})
