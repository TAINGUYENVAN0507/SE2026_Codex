import { describe, expect, it } from 'vitest'
import { ApiError, parseApiError, toNetworkError } from './errors'

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

  it('uses the server message for an unknown error code', async () => {
    const error = await parseApiError(
      response(
        JSON.stringify({
          error: { code: 'NEW_BACKEND_CODE', message: 'Server message' },
        }),
      ),
    )
    expect(error.code).toBe('NEW_BACKEND_CODE')
    expect(error.message).toBe('Server message')
  })
})
