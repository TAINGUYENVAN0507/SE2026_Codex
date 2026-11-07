import { setupWorker } from 'msw/browser'
import { http, HttpResponse } from 'msw'
import jobRetryScheduled from '../../../contracts/fixtures/api/job_retry_scheduled.json'
import { handlers } from './handlers'

// Chỉ cập nhật đồng hồ của bản xem thử trên trình duyệt. Fixture contract/test giữ nguyên.
const previewStartedAt = Date.now() - 94_000
export const worker = setupWorker(
  http.get('*/api/v1/jobs/:jobId', ({ params }) => {
    if (params.jobId !== jobRetryScheduled.id) return
    return HttpResponse.json({
      ...jobRetryScheduled,
      status: 'running',
      stages: { ...jobRetryScheduled.stages, summarize: 'running' },
      attempt: 1,
      next_run_at: null,
      error: null,
      created_at: new Date(previewStartedAt - 1000).toISOString(),
      started_at: new Date(previewStartedAt).toISOString(),
    })
  }),
  ...handlers,
)
