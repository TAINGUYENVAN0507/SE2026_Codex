import type { ApiError } from '../../api/errors'

export const PIPELINE_STAGES = [
  'preprocess',
  'vad',
  'asr',
  'diarize',
  'merge',
  'summarize',
] as const

export type PipelineStage = (typeof PIPELINE_STAGES)[number]
export type JobStatus =
  | 'queued'
  | 'running'
  | 'retry_scheduled'
  | 'succeeded'
  | 'failed'
  | 'cancelled'

export interface JobStatusData {
  status: JobStatus
  current_stage: PipelineStage | null
  completed_stages: PipelineStage[]
  attempt: number
  max_attempts: number
  error: ApiError | null
}
