import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRightIcon } from '@phosphor-icons/react/dist/csr/ArrowUpRight'
import { ApiError, errorMessageForCode } from '../../api/errors'
import type { Job } from '../../api/client'
import { PIPELINE_STAGES, type JobStatus, type PipelineStage } from './model'
import { useJobQuery } from './useJobQuery'
import { formatTime } from '../meetings/model'

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

export function JobStatusCard({
  jobId,
  detailsHref,
}: {
  jobId: string
  detailsHref?: string
}) {
  const { data: job, error, isPending, pollDelayMs } = useJobQuery(jobId)
  const retryAt = job?.status === 'retry_scheduled' ? job.next_run_at : null

  if (isPending)
    return (
      <section
        className={detailsHref ? 'job-status-inline' : 'job-status-card'}
        aria-label="Tiến độ xử lý cuộc họp"
      >
        <p role="status">Đang tải tiến độ xử lý…</p>
      </section>
    )

  if (!job)
    return (
      <section
        className={detailsHref ? 'job-status-inline' : 'job-status-card'}
        aria-label="Tiến độ xử lý cuộc họp"
      >
        <p className="job-error" role="alert">
          {error instanceof ApiError
            ? error.message
            : 'Không tải được tiến độ xử lý. Hãy thử lại sau.'}
        </p>
      </section>
    )

  const pollingNotice = error ? (
    <p className="job-error" role="alert">
      {error instanceof ApiError ? error.message : 'Không tải được tiến độ.'} Tự
      động kiểm tra lại sau {Math.ceil(pollDelayMs / 1000)} giây.
    </p>
  ) : null

  if (detailsHref)
    return (
      <section
        className="job-status-inline"
        aria-label="Tiến độ xử lý cuộc họp"
      >
        <div className="job-inline-label">
          <span
            className="job-inline-dot"
            data-job-state={job.status}
            aria-hidden="true"
          />
          <span role="status" data-status={job.status}>
            {statusLabels[job.status]}
          </span>
          {job.stage && (
            <span className="job-inline-stage">{stageLabels[job.stage]}</span>
          )}
        </div>
        <div className="job-inline-progress">
          <Progress job={job} />
          {job.started_at && <ElapsedTime key={job.started_at} job={job} />}
        </div>
        <Link className="job-details-link" to={detailsHref}>
          Xem tiến độ <ArrowUpRightIcon size={16} />
        </Link>
        {pollingNotice}
        {retryAt && <RetryCountdown key={retryAt} retryAt={retryAt} />}
        {job.status === 'failed' && job.error && (
          <p className="job-inline-error" role="alert">
            {errorMessageForCode(job.error.code)}
          </p>
        )}
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
      <div className="job-progress-row">
        <Progress job={job} />
        {job.started_at && <ElapsedTime key={job.started_at} job={job} />}
      </div>
      {pollingNotice}
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

function Progress({ job }: { job: Job }) {
  return (
    <>
      <div
        className="job-progress"
        role="progressbar"
        aria-label="Tiến độ xử lý"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={job.progress * 100}
        aria-valuetext={`${Math.round(job.progress * 100)}%`}
      >
        <span style={{ width: `${job.progress * 100}%` }} />
      </div>
      <span className="job-percent">{Math.round(job.progress * 100)}%</span>
    </>
  )
}

function ElapsedTime({ job }: { job: Job }) {
  const [now, setNow] = useState(() => Date.now())
  const active = ['queued', 'running', 'retry_scheduled'].includes(job.status)
  useEffect(() => {
    if (!active) return
    const timer = window.setInterval(() => setNow(Date.now()), 1_000)
    return () => window.clearInterval(timer)
  }, [active])
  const start = Date.parse(job.started_at!)
  const end = job.finished_at ? Date.parse(job.finished_at) : now
  if (
    !Number.isFinite(start) ||
    !Number.isFinite(end) ||
    (!active && !job.finished_at)
  )
    return null
  return (
    <span className="job-elapsed">
      Đã chạy {formatTime(Math.max(0, end - start) / 1000)}
    </span>
  )
}
