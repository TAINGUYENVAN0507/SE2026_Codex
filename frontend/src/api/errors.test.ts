import { describe, expect, it } from 'vitest'
import {
  ApiError,
  parseApiError,
  toNetworkError,
  serviceBusyMessage,
} from './errors'

function response(body: string, contentType = 'application/json') {
  return new Response(body, {
    status: 400,
    headers: { 'Content-Type': contentType },
  })
}

describe('API errors', () => {
  it('parses the backend error envelope and maps known messages', async () => {
    const error = await parseApiError(
      response(
        JSON.stringify({
          error: {
            code: 'AUDIO_TOO_LONG',
            message: 'Audio duration exceeds limit',
            details: { duration_sec: 7200 },
            request_id: 'req-123',
          },
        }),
      ),
    )

    expect(error).toBeInstanceOf(ApiError)
    expect(error.code).toBe('AUDIO_TOO_LONG')
    expect(error.message).toContain('thời lượng')
    expect(error.details).toEqual({ duration_sec: 7200 })
    expect(error.request_id).toBe('req-123')
  })

  it('uses a safe fallback when required envelope fields are missing', async () => {
    const error = await parseApiError(
      response(JSON.stringify({ error: { code: 'BROKEN' } })),
    )
    expect(error.code).toBe('UNKNOWN_ERROR')
  })

  it('handles an HTML error response', async () => {
    const error = await parseApiError(
      response('<html>failed</html>', 'text/html'),
    )
    expect(error.code).toBe('UNKNOWN_ERROR')
  })

  it('normalizes a network failure', () => {
    expect(toNetworkError().code).toBe('NETWORK_ERROR')
  })

  it('hides unrecognized server messages that might contain private data', async () => {
    const error = await parseApiError(
      response(
        JSON.stringify({
          error: {
            code: 'NEW_BACKEND_CODE',
            message: 'CANARY_TRANSCRIPT_STACK_TRACE',
          },
        }),
      ),
    )
    expect(error.code).toBe('NEW_BACKEND_CODE')
    expect(error.message).toBe('Đã xảy ra lỗi không xác định. Hãy thử lại sau.')
    expect(error.message).not.toContain('CANARY_TRANSCRIPT')
  })
})

it('giữ danh sách vị trí lỗi 422 để form gắn lỗi đúng trường, không lộ message máy chủ', async () => {
  const details = [
    {
      loc: ['body', 'meeting_date'],
      type: 'string_pattern_mismatch',
      msg: 'CANARY_RAW',
    },
  ]
  const error = await parseApiError(
    new Response(
      JSON.stringify({
        error: {
          code: 'VALIDATION_ERROR',
          message: 'CANARY_RAW',
          details,
          request_id: null,
        },
      }),
      { status: 422 },
    ),
  )
  expect(error.details).toEqual(details)
  expect(error.message).not.toContain('CANARY_RAW')
  expect(error.status).toBe(422)
})

it.each([
  [null, 'ít'],
  [0, '1'],
  [1200, '2'],
  [2000, '2'],
] as const)(
  'FE-03: busy message rounds %s ms to %s seconds',
  (delay, seconds) => {
    const error = new ApiError(
      'SERVICE_UNAVAILABLE',
      'CANARY_BUSY',
      null,
      null,
      503,
      delay,
    )
    expect(serviceBusyMessage(error)).toBe(
      `Máy chủ đang bận. Vui lòng thử lại sau ${seconds} giây.`,
    )
  },
)
