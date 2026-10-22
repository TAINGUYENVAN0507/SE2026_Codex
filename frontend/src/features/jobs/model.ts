import type { Job } from '../../api/client'

export const PIPELINE_STAGES = [
  'preprocess',
  'vad',
  'asr',
  'diarize',
  'merge',
  'summarize',
] as const

export type PipelineStage = (typeof PIPELINE_STAGES)[number]
export type JobStatus = Job['status']
