import { afterEach, describe, expect, it, vi } from 'vitest'
import { uploadMeeting } from './uploadMeeting'

class FakeXHR {
  static instances: FakeXHR[] = []
  upload = { onprogress: null as ((event: ProgressEvent) => void) | null }
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  onabort: (() => void) | null = null
  status = 0
  responseText = ''
  withCredentials = false
  headers: Record<string, string> = {}
  body?: FormData
  method = ''
  url = ''
  constructor() {
    FakeXHR.instances.push(this)
  }
  open(method: string, url: string) {
    this.method = method
    this.url = url
  }
  setRequestHeader(key: string, value: string) {
    this.headers[key] = value
  }
  send(body: FormData) {
    this.body = body
  }
  abort() {
    this.onabort?.()
  }
  progress(loaded: number, total: number) {
    this.upload.onprogress?.({
      lengthComputable: true,
      loaded,
      total,
    } as ProgressEvent)
  }
  finish(status: number, body: unknown) {
    this.status = status
    this.responseText = JSON.stringify(body)
    this.onload?.()
  }
}

const originalXHR = globalThis.XMLHttpRequest
afterEach(() => {
  globalThis.XMLHttpRequest = originalXHR
  FakeXHR.instances = []
})
const file = new File(['audio'], 'meeting.wav', { type: 'audio/wav' })
const form = {
  title: 'Họp',
  meetingDate: '2026-10-22',
  source: 'upload' as const,
}

describe('FE-05 XHR upload', () => {
  it('sends multipart with consent and idempotency key; reports progress', async () => {
    globalThis.XMLHttpRequest = FakeXHR as unknown as typeof XMLHttpRequest
    const onProgress = vi.fn()
    const upload = uploadMeeting(file, form, 'same-key', onProgress)
    const xhr = FakeXHR.instances[0]
    expect([xhr.method, xhr.url, xhr.headers['Idempotency-Key']]).toEqual([
      'POST',
      '/api/v1/meetings',
      'same-key',
    ])
    expect(xhr.body?.get('file')).toBe(file)
    expect(xhr.body?.get('consent_confirmed')).toBe('true')
    xhr.progress(5, 10)
    xhr.progress(10, 10)
    expect(onProgress.mock.calls.map(([value]) => value)).toEqual([50, 100])
    xhr.finish(201, { meeting: { id: 'meeting-1' }, job: {} })
    expect((await upload.promise).meeting.id).toBe('meeting-1')
  })

  it('cancel rejects and retry uses the same key', async () => {
    globalThis.XMLHttpRequest = FakeXHR as unknown as typeof XMLHttpRequest
    const first = uploadMeeting(file, form, 'retry-key', vi.fn())
    first.abort()
    await expect(first.promise).rejects.toMatchObject({
      code: 'UPLOAD_CANCELLED',
    })
    const retry = uploadMeeting(file, form, 'retry-key', vi.fn())
    expect(
      FakeXHR.instances.map((xhr) => xhr.headers['Idempotency-Key']),
    ).toEqual(['retry-key', 'retry-key'])
    FakeXHR.instances[1].finish(201, { meeting: { id: 'ok' } })
    await expect(retry.promise).resolves.toHaveProperty('meeting.id', 'ok')
  })

  it.each([
    [400, 'BAD_REQUEST'],
    [409, 'CONFLICT'],
    [413, 'FILE_TOO_LARGE'],
    [415, 'UNSUPPORTED_MEDIA_TYPE'],
    [422, 'CONSENT_REQUIRED'],
  ])('maps HTTP %i / %s to a Vietnamese ApiError', async (status, code) => {
    globalThis.XMLHttpRequest = FakeXHR as unknown as typeof XMLHttpRequest
    const request = uploadMeeting(file, form, 'key', vi.fn())
    FakeXHR.instances[0].finish(status, {
      error: {
        code,
        message: 'Backend message',
        details: null,
        request_id: null,
      },
    })
    await expect(request.promise).rejects.toMatchObject({
      name: 'ApiError',
      code,
      message: expect.not.stringContaining('Backend message'),
    })
  })
})
