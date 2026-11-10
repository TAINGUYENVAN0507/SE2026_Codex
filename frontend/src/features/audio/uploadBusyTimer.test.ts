import { afterEach, expect, it, vi } from 'vitest'
import { uploadMeeting } from './uploadMeeting'

class Request {
  static sent: Request[] = []
  upload = { onprogress: null }
  onload: (() => void) | null = null
  onabort: (() => void) | null = null
  onerror: (() => void) | null = null
  withCredentials = false
  status = 503
  responseText = JSON.stringify({
    error: { code: 'SERVICE_UNAVAILABLE', message: 'busy' },
  })
  open() {}
  setRequestHeader() {}
  getResponseHeader() {
    return null
  }
  send() {
    Request.sent.push(this)
  }
  abort() {
    this.onabort?.()
  }
}
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  Request.sent = []
})

it('missing Retry-After waits 2 seconds; abort cancels a queued retry', async () => {
  vi.useFakeTimers()
  vi.stubGlobal('XMLHttpRequest', Request)
  const busy = vi.fn()
  const upload = uploadMeeting(
    new File(['audio'], 'test.wav'),
    { title: 'Test', meetingDate: '2026-11-10', source: 'upload' },
    'unchanged',
    vi.fn(),
    busy,
  )
  Request.sent[0].onload?.()
  await vi.advanceTimersByTimeAsync(0)
  expect(busy).toHaveBeenCalledWith(1, 2000)
  await vi.advanceTimersByTimeAsync(1999)
  expect(Request.sent).toHaveLength(1)
  await vi.advanceTimersByTimeAsync(1)
  expect(Request.sent).toHaveLength(2)
  Request.sent[1].onload?.()
  await vi.advanceTimersByTimeAsync(0)
  const rejected = expect(upload.promise).rejects.toMatchObject({
    code: 'UPLOAD_CANCELLED',
  })
  upload.abort()
  await rejected
  await vi.advanceTimersByTimeAsync(60_000)
  expect(Request.sent).toHaveLength(2)
})
