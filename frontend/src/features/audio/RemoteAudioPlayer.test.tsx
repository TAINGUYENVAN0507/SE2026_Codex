import { createRef } from 'react'
import {
  act,
  render,
  screen,
  fireEvent,
  cleanup,
  waitFor,
} from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import {
  beforeAll,
  afterAll,
  afterEach,
  beforeEach,
  expect,
  it,
  vi,
} from 'vitest'
import { RemoteAudioPlayer } from './RemoteAudioPlayer'
import * as apiErrors from '../../api/errors'
import type { PlayerHandle } from './AudioPlayer'

const server = setupServer()
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-11-26T12:00:00Z'))
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
})
afterEach(() => {
  cleanup()
  server.resetHandlers()
  vi.restoreAllMocks()
  vi.useRealTimers()
})
afterAll(() => server.close())
function setup(
  available = true,
  retentionUntil: string | null = '2026-11-20T12:00:00Z',
) {
  const handle = createRef<PlayerHandle>()
  const view = render(
    <>
      <RemoteAudioPlayer
        meetingId="test"
        audioInfo={{ available, retention_until: retentionUntil }}
        duration={120}
        onPosition={vi.fn()}
        onFile={vi.fn()}
        ref={handle}
      />
      <p>Transcript vẫn đọc được</p>
    </>,
  )
  return { ...view, handle }
}
it('shows expired audio without losing the transcript when available=false', () => {
  const { container } = setup(false)
  expect(screen.getByRole('status')).toHaveTextContent(
    'Audio đã hết hạn lưu trữ',
  )
  expect(container.querySelector('audio')).toBeNull()
  expect(screen.getByText('Transcript vẫn đọc được')).toBeInTheDocument()
  expect(container.querySelector('time')).toHaveAttribute(
    'datetime',
    '2026-11-20T12:00:00Z',
  )
  expect(container.querySelector('time')?.textContent).toBe(
    new Intl.DateTimeFormat('vi-VN', {
      dateStyle: 'short',
      timeStyle: 'short',
    }).format(new Date('2026-11-20T12:00:00Z')),
  )
})
it('classifies a real 410 response as expired after a media error', async () => {
  server.use(
    http.get('*/api/v1/meetings/test/audio', ({ request }) => {
      expect(request.headers.get('Range')).toBe('bytes=0-0')
      return new HttpResponse(null, { status: 410 })
    }),
  )
  const { container } = setup()
  const audio = container.querySelector('audio')!
  expect(audio.getAttribute('src')).toBe('/api/v1/meetings/test/audio')
  fireEvent.error(audio)
  expect(await screen.findByRole('status')).toHaveTextContent(
    'Audio đã hết hạn lưu trữ',
  )
  expect(screen.getByText('Transcript vẫn đọc được')).toBeInTheDocument()
})
it('does not label a network/server failure as expired', async () => {
  server.use(
    http.get(
      '*/api/v1/meetings/test/audio',
      () => new HttpResponse(null, { status: 500 }),
    ),
  )
  const { container } = setup()
  fireEvent.error(container.querySelector('audio')!)
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Trình duyệt không đọc được file audio này',
  )
  expect(screen.queryByText('Audio đã hết hạn lưu trữ')).not.toBeInTheDocument()
})
it('seeks server audio to the evidence timestamp', () => {
  const { container, handle } = setup()
  act(() => handle.current!.seek(18.5))
  expect(container.querySelector('audio')!.currentTime).toBe(18.5)
})

it.each(['2026-12-20T12:00:00Z', null])(
  'FE-19: unavailable chưa hết hạn (%s) báo mất file, vẫn giữ transcript',
  (retention) => {
    const { container } = setup(false, retention)
    expect(screen.getByRole('status')).toHaveTextContent(
      'Không tìm thấy file audio',
    )
    expect(
      screen.queryByText('Audio đã hết hạn lưu trữ'),
    ).not.toBeInTheDocument()
    expect(container.querySelector('audio')).toBeNull()
    expect(screen.getByText('Transcript vẫn đọc được')).toBeVisible()
  },
)

it.each(['AUDIO_NOT_FOUND'])(
  'FE-19: probe 404 %s báo mất file thay cho lỗi phát chung',
  async (code) => {
    server.use(
      http.get('*/api/v1/meetings/test/audio', ({ request }) => {
        expect(request.headers.get('Range')).toBe('bytes=0-0')
        return HttpResponse.json(
          {
            error: {
              code,
              message: 'CANARY_RAW_AUDIO',
              details: null,
              request_id: null,
            },
          },
          { status: 404 },
        )
      }),
    )
    const { container } = setup(true, '2026-12-20T12:00:00Z')
    fireEvent.error(container.querySelector('audio')!)
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Không tìm thấy file audio',
    )
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByText('Transcript vẫn đọc được')).toBeVisible()
    expect(screen.queryByText('CANARY_RAW_AUDIO')).not.toBeInTheDocument()
  },
)

it('FE-19: NOT_FOUND means no meeting and keeps the generic playback error', async () => {
  const parse = vi.spyOn(apiErrors, 'parseApiError')
  server.use(
    http.get('*/api/v1/meetings/test/audio', () =>
      HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: 'CANARY_RAW_AUDIO' } },
        { status: 404 },
      ),
    ),
  )
  const { container } = setup(true, '2026-12-20T12:00:00Z')
  fireEvent.error(container.querySelector('audio')!)
  await waitFor(() => expect(parse).toHaveBeenCalledOnce())
  await act(async () => {
    // Chờ probe đọc xong JSON trước khi kiểm nhánh không được đổi sang mất file.
    await parse.mock.results[0].value
  })
  expect(screen.getByRole('alert')).toHaveTextContent(
    'Trình duyệt không đọc được file audio này',
  )
  expect(
    screen.queryByText('Không tìm thấy file audio'),
  ).not.toBeInTheDocument()
  expect(screen.queryByText('Audio đã hết hạn lưu trữ')).not.toBeInTheDocument()
  expect(container.querySelector('audio')).not.toBeNull()
  expect(screen.getByText('Transcript vẫn đọc được')).toBeVisible()
  expect(screen.queryByText('CANARY_RAW_AUDIO')).not.toBeInTheDocument()
})
