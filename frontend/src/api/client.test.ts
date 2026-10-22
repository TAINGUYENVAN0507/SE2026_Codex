import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import meetingProcessing from '../../../contracts/fixtures/api/meeting_processing.json'
import jobRetryScheduled from '../../../contracts/fixtures/api/job_retry_scheduled.json'
import { handlers } from '../mocks/handlers'
import { getJob, getMeeting } from './client'

const server = setupServer(...handlers)
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('typed API client', () => {
  it('returns the committed contract fixtures', async () => {
    const meeting = await getMeeting(meetingProcessing.id)
    const job = await getJob(jobRetryScheduled.id)
    expect(meeting).toEqual(meetingProcessing)
    expect(job).toEqual(jobRetryScheduled)

    // Kiểm tra các field bắt buộc, không chỉ so fixture với chính nó.
    expect(meeting).toMatchObject({
      id: meetingProcessing.id,
      title: expect.any(String),
      source: expect.stringMatching(/^(upload|recording)$/),
      status: expect.stringMatching(
        /^(queued|processing|ready|partial|failed)$/,
      ),
      audio: expect.objectContaining({ available: expect.any(Boolean) }),
      artifacts: expect.objectContaining({ transcript: expect.any(String) }),
      created_at: expect.any(String),
      version: expect.any(Number),
    })
    expect(job).toMatchObject({
      id: jobRetryScheduled.id,
      meeting_id: meeting.id,
      status: expect.stringMatching(
        /^(queued|running|retry_scheduled|succeeded|failed|cancelled)$/,
      ),
      progress: expect.any(Number),
      attempt: expect.any(Number),
      max_attempts: expect.any(Number),
      created_at: expect.any(String),
    })
  })

  it('maps a 404 error envelope to ApiError', async () => {
    await expect(getMeeting('missing')).rejects.toMatchObject({
      name: 'ApiError',
      code: 'NOT_FOUND',
    })
  })

  it('maps network errors to ApiError', async () => {
    server.use(http.get('*/api/v1/jobs/:jobId', () => HttpResponse.error()))
    await expect(getJob('job-1')).rejects.toMatchObject({
      name: 'ApiError',
      code: 'NETWORK_ERROR',
    })
  })
})
