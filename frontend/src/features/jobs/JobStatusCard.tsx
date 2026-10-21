import {
  PIPELINE_STAGES,
  type JobStatus,
  type JobStatusData,
  type PipelineStage,
} from './model'

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

function stageState(stage: PipelineStage, job: JobStatusData) {
  if (job.status === 'succeeded' || job.completed_stages.includes(stage))
    return 'completed'
  if (stage === job.current_stage) {
    if (job.status === 'failed') return 'failed'
    if (job.status === 'retry_scheduled') return 'retry'
    if (job.status === 'cancelled') return 'cancelled'
    return 'current'
  }
  if (job.status === 'queued' && stage === PIPELINE_STAGES[0]) return 'current'
  return 'pending'
}

export function JobStatusCard({ job }: { job: JobStatusData }) {
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
      {job.status === 'failed' && job.error && (
        <p className="job-error" role="alert">
          {job.error.message}
        </p>
      )}
    </section>
  )
}
