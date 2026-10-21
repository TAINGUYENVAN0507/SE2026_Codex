import { afterEach, describe, expect, it, vi } from 'vitest'
import { getJob, getMeeting } from './client'
import { ApiError } from './errors'

afterEach(() => vi.unstubAllGlobals())

describe('typed API client', () => {
  it('returns a meeting from the contract endpoint with cookies', async () => {
    const payload = { id: 'meeting-1', title: 'Họp thử' }
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(getMeeting('meeting-1')).resolves.toEqual(payload)
    const [request] = fetchMock.mock.calls[0] as [Request]
    expect(request.url).toContain('/api/v1/meetings/meeting-1')
    expect(request.credentials).toBe('include')
  })

  it('maps a 404 error envelope to ApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: 'MEETING_NOT_FOUND',
              message: 'Không tìm thấy cuộc họp.',
              details: null,
              request_id: 'req-404',
            },
          }),
          { status: 404, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    )

    await expect(getMeeting('missing')).rejects.toMatchObject({
      name: 'ApiError',
      code: 'MEETING_NOT_FOUND',
      request_id: 'req-404',
    })
  })

  it('maps network errors to ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    await expect(getJob('job-1')).rejects.toMatchObject({
      name: 'ApiError',
      code: 'NETWORK_ERROR',
    } satisfies Partial<ApiError>)
  })
})
