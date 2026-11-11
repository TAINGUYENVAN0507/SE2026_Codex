import { useEffect, useState } from 'react'
import type { Job } from '../../api/client'
import { formatTime } from '../meetings/model'

function timestamp(value: string | null | undefined): number | null {
  if (!value) return null
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) ? parsed : null
}
const localTime = new Intl.DateTimeFormat('vi-VN', {
  dateStyle: 'short',
  timeStyle: 'medium',
})

export function JobTimes({
  job,
  compact = false,
}: {
  job: Job
  compact?: boolean
}) {
  const [now, setNow] = useState(() => Date.now())
  const active = ['queued', 'running', 'retry_scheduled'].includes(job.status)
  useEffect(() => {
    if (!active) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [active])
  const created = timestamp(job.created_at)
  const started = timestamp(job.started_at)
  const finished = timestamp(job.finished_at)
  const waitEnd = started ?? finished ?? (active ? now : null)
  const elapsedEnd = finished ?? (active ? now : null)
  const wait =
    created !== null && waitEnd !== null ? Math.max(0, waitEnd - created) : null
  const elapsed =
    started !== null && elapsedEnd !== null
      ? Math.max(0, elapsedEnd - started)
      : null
  if (
    wait === null &&
    elapsed === null &&
    started === null &&
    finished === null
  )
    return null
  return (
    <div
      className={compact ? 'job-times compact' : 'job-times'}
      aria-label="Thời gian xử lý"
    >
      {wait !== null && <span>Đã chờ {formatTime(wait / 1000)}</span>}
      {elapsed !== null && (
        <span className="job-elapsed">
          Đã chạy {formatTime(elapsed / 1000)}
        </span>
      )}
      {!compact && started !== null && (
        <span>
          Bắt đầu:{' '}
          <time aria-label="Giờ bắt đầu" dateTime={job.started_at!}>
            {localTime.format(started)}
          </time>
        </span>
      )}
      {!compact && finished !== null && (
        <span>
          Hoàn thành:{' '}
          <time aria-label="Giờ hoàn thành" dateTime={job.finished_at!}>
            {localTime.format(finished)}
          </time>
        </span>
      )}
    </div>
  )
}
