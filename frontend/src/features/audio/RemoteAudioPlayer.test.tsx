import { createRef } from 'react'
import { act, render, screen, fireEvent, cleanup } from '@testing-library/react'
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
import type { PlayerHandle } from './AudioPlayer'

const server = setupServer()
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
beforeEach(() =>
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {}),
)
afterEach(() => {
  cleanup()
  server.resetHandlers()
  vi.restoreAllMocks()
})
afterAll(() => server.close())
function setup(available = true) {
  const handle = createRef<PlayerHandle>()
  const view = render(
    <>
      <RemoteAudioPlayer
        meetingId="test"
        audioInfo={{ available, retention_until: '2026-11-20T12:00:00Z' }}
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
