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
    await expect(getMeeting(meetingProcessing.id)).resolves.toEqual(
      meetingProcessing,
    )
    await expect(getJob(jobRetryScheduled.id)).resolves.toEqual(
      jobRetryScheduled,
    )
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
