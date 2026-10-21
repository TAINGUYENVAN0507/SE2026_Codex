import { http, HttpResponse } from 'msw'
import meetingProcessing from '../../../contracts/fixtures/api/meeting_processing.json'
import jobRetryScheduled from '../../../contracts/fixtures/api/job_retry_scheduled.json'

function notFound(message: string) {
  return HttpResponse.json(
    { error: { code: 'NOT_FOUND', message, details: null, request_id: null } },
    { status: 404 },
  )
}

export const handlers = [
  http.get('*/api/v1/meetings/:meetingId', ({ params }) =>
    params.meetingId === meetingProcessing.id
      ? HttpResponse.json(meetingProcessing)
      : notFound('Không tìm thấy cuộc họp.'),
  ),
  http.get('*/api/v1/jobs/:jobId', ({ params }) =>
    params.jobId === jobRetryScheduled.id
      ? HttpResponse.json(jobRetryScheduled)
      : notFound('Không tìm thấy job.'),
  ),
]
