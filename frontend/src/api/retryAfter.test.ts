import { expect, it } from 'vitest'
import { retryAfterMs } from './retryAfter'
import { parseApiError } from './errors'

it('reads seconds, HTTP date, and rejects missing or invalid Retry-After', () => {
  const now = Date.parse('2026-11-10T00:00:00Z')
  expect(retryAfterMs('2', now)).toBe(2000)
  expect(retryAfterMs('0', now)).toBe(0)
  expect(retryAfterMs('Tue, 10 Nov 2026 00:00:05 GMT', now)).toBe(5000)
  expect(retryAfterMs(null, now)).toBeNull()
  expect(retryAfterMs('not-a-date', now)).toBeNull()
  expect(retryAfterMs('-1', now)).toBeNull()
})

it('preserves Retry-After in safe API errors without exposing backend text', async () => {
  const error = await parseApiError(
    new Response(
      JSON.stringify({
        error: { code: 'SERVICE_UNAVAILABLE', message: 'RAW_CANARY' },
      }),
      { status: 503, headers: { 'Retry-After': '7' } },
    ),
  )
  expect(error.retryAfterMs).toBe(7000)
  expect(error.message).not.toContain('RAW_CANARY')
})
