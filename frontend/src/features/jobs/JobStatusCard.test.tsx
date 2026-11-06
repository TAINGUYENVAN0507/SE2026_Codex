import { act, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
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

function renderCard(compact = false) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <JobStatusCard
          jobId={jobId}
          detailsHref={compact ? '/meetings/example/processing' : undefined}
        />
      </MemoryRouter>
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
  it('keeps progress and retry visible in compact mode and links to a separate stage view', async () => {
    renderCard(true)
    const link = await screen.findByRole('link', { name: 'Xem tiến độ' })
    expect(link).toHaveAttribute('href', '/meetings/example/processing')
    expect(screen.getByRole('progressbar')).toHaveAttribute(
      'aria-valuenow',
      '90',
    )
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
    expect(screen.getByRole('timer')).toBeInTheDocument()
  })
  it.each([0, 0.42, 1])(
    'exposes server progress %s as an accessible percentage',
    async (progress) => {
      server.use(
        http.get('*/api/v1/jobs/:jobId', () =>
          HttpResponse.json({
            ...jobWithStatus('running'),
            progress,
            started_at: null,
          }),
        ),
      )
      renderCard()
      const bar = await screen.findByRole('progressbar', {
        name: 'Tiến độ xử lý',
      })
      expect(bar).toHaveAttribute('aria-valuenow', String(progress * 100))
      expect(screen.queryByText(/Đã chạy/)).not.toBeInTheDocument()
    },
  )

  it('updates elapsed time from started_at and stops at finished_at', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-06T00:01:00Z'))
    server.use(
      http.get('*/api/v1/jobs/:jobId', () =>
        HttpResponse.json({
          ...jobWithStatus('running'),
          started_at: '2026-11-06T00:00:00Z',
          finished_at: null,
        }),
      ),
    )
    renderCard()
    await act(async () => vi.advanceTimersByTimeAsync(100))
    expect(screen.getByText('Đã chạy 01:00')).toBeInTheDocument()
    await act(async () => vi.advanceTimersByTimeAsync(1000))
    expect(screen.getByText('Đã chạy 01:01')).toBeInTheDocument()
  })

  it('uses finished_at instead of the current time for a completed job', async () => {
    server.use(
      http.get('*/api/v1/jobs/:jobId', () =>
        HttpResponse.json({
          ...jobWithStatus('succeeded'),
          started_at: '2026-11-06T00:00:00Z',
          finished_at: '2026-11-06T00:01:12Z',
        }),
      ),
    )
    renderCard()
    expect(await screen.findByText('Đã chạy 01:12')).toBeInTheDocument()
  })
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
        'File audio không hợp lệ hoặc không thể đọc.',
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

  it('counts down to the server next_run_at and clears the timer on unmount', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(
      new Date(Date.parse(jobRetryScheduled.next_run_at) - 10_000),
    )
    const { unmount } = renderCard()
    await act(async () => vi.advanceTimersByTimeAsync(100))
    expect(screen.getByRole('timer')).toHaveTextContent(
      'Đang thử lại sau 10 giây',
    )
    await act(async () => vi.advanceTimersByTimeAsync(1_000))
    expect(screen.getByRole('timer')).toHaveTextContent(
      'Đang thử lại sau 9 giây',
    )
    unmount()
    expect(screen.queryByRole('timer')).not.toBeInTheDocument()
  })

  it('starts the countdown from response time after a delayed job response', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(
      new Date(Date.parse(jobRetryScheduled.next_run_at) - 10_000),
    )
    let release: () => void = () => {}
    const waiting = new Promise<void>((resolve) => {
      release = resolve
    })
    server.use(
      http.get('*/api/v1/jobs/:jobId', async () => {
        await waiting
        return HttpResponse.json(jobRetryScheduled)
      }),
    )
    renderCard()
    await act(async () => vi.advanceTimersByTimeAsync(3_000))
    await act(async () => {
      release()
      await vi.advanceTimersByTimeAsync(100)
    })
    expect(screen.getByRole('timer')).toHaveTextContent(
      'Đang thử lại sau 7 giây',
    )
  })

  it.each([
    ['AUDIO_INVALID', 'File audio không hợp lệ hoặc không thể đọc.'],
    ['UNRECOGNIZED_CODE', 'Đã xảy ra lỗi không xác định. Hãy thử lại sau.'],
  ])('does not render raw server messages for %s', async (code, expected) => {
    server.use(
      http.get('*/api/v1/jobs/:jobId', () =>
        HttpResponse.json({
          ...jobWithStatus('failed'),
          error: { code, message: 'CANARY_TECHNICAL_TRACE_do_not_show' },
        }),
      ),
    )
    renderCard()
    expect(await screen.findByRole('alert')).toHaveTextContent(expected)
    expect(
      screen.queryByText('CANARY_TECHNICAL_TRACE_do_not_show'),
    ).not.toBeInTheDocument()
  })
})
