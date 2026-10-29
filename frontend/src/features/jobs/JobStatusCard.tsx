import { useEffect, useState } from 'react'
import { ApiError, errorMessageForCode } from '../../api/errors'
import type { Job } from '../../api/client'
import { PIPELINE_STAGES, type JobStatus, type PipelineStage } from './model'
import { useJobQuery } from './useJobQuery'

const stageLabels: Record<PipelineStage, string> = {
  preprocess: 'Chuẩn bị audio',
  vad: 'Phát hiện đoạn nói',
  asr: 'Nhận dạng giọng nói',
  diarize: 'Phân biệt người nói',
  merge: 'Ghép transcript',
  summarize: 'Tạo tóm tắt',
}

const statusLabels: Record<JobStatus, string> = {
  queued: 'Đang chờ xử lý',
  running: 'Đang xử lý',
  retry_scheduled: 'Đã lên lịch thử lại',
  succeeded: 'Hoàn tất xử lý',
  failed: 'Xử lý thất bại',
  cancelled: 'Đã hủy xử lý',
}

function stageState(stage: PipelineStage, job: Job) {
  if (job.status === 'succeeded' || job.stages?.[stage] === 'succeeded')
    return 'completed'
  if (stage === job.stage) {
    if (job.status === 'failed') return 'failed'
    if (job.status === 'retry_scheduled') return 'retry'
    if (job.status === 'cancelled') return 'cancelled'
    return 'current'
  }
  if (job.status === 'queued' && stage === PIPELINE_STAGES[0]) return 'current'
  return 'pending'
}

function RetryCountdown({ retryAt }: { retryAt: string }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1_000)
    return () => window.clearInterval(timer)
  }, [])
  const seconds = Math.max(0, Math.ceil((Date.parse(retryAt) - now) / 1_000))
  return (
    <p role="timer" aria-label="Thời gian chờ thử lại">
      {seconds > 0 ? `Đang thử lại sau ${seconds} giây` : 'Đang thử lại…'}
    </p>
  )
}

export function JobStatusCard({ jobId }: { jobId: string }) {
  const { data: job, error, isPending } = useJobQuery(jobId)
  const retryAt = job?.status === 'retry_scheduled' ? job.next_run_at : null

  if (isPending)
    return (
      <section className="job-status-card" aria-label="Tiến độ xử lý cuộc họp">
        <p role="status">Đang tải tiến độ xử lý…</p>
      </section>
    )

  if (error || !job)
    return (
      <section className="job-status-card" aria-label="Tiến độ xử lý cuộc họp">
        <p className="job-error" role="alert">
          {error instanceof ApiError
            ? error.message
            : 'Không tải được tiến độ xử lý. Hãy thử lại sau.'}
        </p>
      </section>
    )

  return (
    <section className="job-status-card" aria-label="Tiến độ xử lý cuộc họp">
      <header className="job-status-header">
        <div>
          <h2>Tiến độ xử lý</h2>
          <p role="status" data-status={job.status}>
            {statusLabels[job.status]}
          </p>
        </div>
        <span className="job-attempt">
          Lượt thử {job.attempt}/{job.max_attempts}
        </span>
      </header>
      <ol className="job-stage-list">
        {PIPELINE_STAGES.map((stage) => {
          const state = stageState(stage, job)
          return (
            <li
              key={stage}
              className="job-stage"
              data-state={state}
              aria-current={state === 'current' ? 'step' : undefined}
            >
              <span className="job-stage-marker" aria-hidden="true" />
              <span>{stageLabels[stage]}</span>
              <span className="job-stage-state">
                {state === 'completed'
                  ? 'Hoàn thành'
                  : state === 'current'
                    ? 'Đang chạy'
                    : state === 'retry'
                      ? 'Chờ thử lại'
                      : state === 'failed'
                        ? 'Thất bại'
                        : state === 'cancelled'
                          ? 'Đã hủy'
                          : 'Chưa bắt đầu'}
              </span>
            </li>
          )
        })}
      </ol>
      {retryAt && <RetryCountdown key={retryAt} retryAt={retryAt} />}
      {job.status === 'failed' && job.error && (
        <p className="job-error" role="alert">
          {errorMessageForCode(job.error.code)}
        </p>
      )}
    </section>
  )
}
