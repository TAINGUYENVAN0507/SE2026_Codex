import { act, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from 'vitest'
import jobRetryScheduled from '../../../../contracts/fixtures/api/job_retry_scheduled.json'
import type { Job } from '../../api/client'
import { handlers } from '../../mocks/handlers'
import { JobStatusCard } from './JobStatusCard'
import { PIPELINE_STAGES, type JobStatus } from './model'

const jobId = jobRetryScheduled.id
const server = setupServer(...handlers)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  vi.useRealTimers()
  server.resetHandlers()
})
afterAll(() => server.close())

function renderCard() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={client}>
      <JobStatusCard jobId={jobId} />
    </QueryClientProvider>,
  )
}

function jobWithStatus(status: JobStatus): Job {
  return {
    ...jobRetryScheduled,
    status,
    stage: status === 'queued' ? null : 'summarize',
    error:
      status === 'failed'
        ? { code: 'AUDIO_INVALID', message: 'File audio không hợp lệ.' }
        : null,
  } as Job
}

describe('JobStatusCard', () => {
  it('shows all six stages from the contract fixture', async () => {
    renderCard()
    await screen.findByText('Đã lên lịch thử lại')
    expect(
      within(screen.getByRole('list')).getAllByRole('listitem'),
    ).toHaveLength(6)
    expect(PIPELINE_STAGES).toEqual([
      'preprocess',
      'vad',
      'asr',
      'diarize',
      'merge',
      'summarize',
    ])
    expect(screen.getByText('Lượt thử 2/3')).toBeInTheDocument()
    expect(screen.getByText('Chờ thử lại')).toBeInTheDocument()
  })

  it.each([
    ['queued', 'Đang chờ xử lý'],
    ['running', 'Đang xử lý'],
    ['retry_scheduled', 'Đã lên lịch thử lại'],
    ['succeeded', 'Hoàn tất xử lý'],
    ['failed', 'Xử lý thất bại'],
    ['cancelled', 'Đã hủy xử lý'],
  ] as const)('renders job status %s', async (status, label) => {
    server.use(
      http.get('*/api/v1/jobs/:jobId', () =>
        HttpResponse.json(jobWithStatus(status)),
      ),
    )
    renderCard()
    expect(await screen.findByText(label)).toBeInTheDocument()
    if (status === 'failed')
      expect(screen.getByRole('alert')).toHaveTextContent(
        'File audio không hợp lệ.',
      )
  })

  it('polls active jobs every 2 seconds and stops after success', async () => {
    let requests = 0
    server.use(
      http.get('*/api/v1/jobs/:jobId', () => {
        requests += 1
        return HttpResponse.json(
          jobWithStatus(requests >= 3 ? 'succeeded' : 'running'),
        )
      }),
    )
    vi.useFakeTimers()
    renderCard()
    await act(async () => vi.advanceTimersByTimeAsync(100))
    expect(screen.getByText('Đang xử lý')).toBeInTheDocument()
    expect(requests).toBe(1)

    await act(async () => vi.advanceTimersByTimeAsync(2_000))
    expect(requests).toBe(2)
    await act(async () => vi.advanceTimersByTimeAsync(2_000))
    expect(requests).toBe(3)
    expect(screen.getByText('Hoàn tất xử lý')).toBeInTheDocument()
    await act(async () => vi.advanceTimersByTimeAsync(6_000))
    expect(requests).toBe(3)
  })

  it.each(['queued', 'retry_scheduled'] as const)(
    'continues polling while the job is %s',
    async (status) => {
      let requests = 0
      server.use(
        http.get('*/api/v1/jobs/:jobId', () => {
          requests += 1
          return HttpResponse.json(jobWithStatus(status))
        }),
      )
      vi.useFakeTimers()
      renderCard()
      await act(async () => vi.advanceTimersByTimeAsync(100))
      expect(requests).toBe(1)
      await act(async () => vi.advanceTimersByTimeAsync(2_000))
      expect(requests).toBe(2)
    },
  )

  it.each(['failed', 'cancelled'] as const)(
    'stops polling when the job is %s',
    async (status) => {
      let requests = 0
      server.use(
        http.get('*/api/v1/jobs/:jobId', () => {
          requests += 1
          return HttpResponse.json(jobWithStatus(status))
        }),
      )
      vi.useFakeTimers()
      renderCard()
      await act(async () => vi.advanceTimersByTimeAsync(100))
      expect(requests).toBe(1)
      await act(async () => vi.advanceTimersByTimeAsync(6_000))
      expect(requests).toBe(1)
    },
  )

  it('shows a localized ApiError when the network fails', async () => {
    server.use(http.get('*/api/v1/jobs/:jobId', () => HttpResponse.error()))
    renderCard()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Không thể kết nối máy chủ.',
    )
  })
})
