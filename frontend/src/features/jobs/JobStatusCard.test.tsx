import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ApiError } from '../../api/errors'
import { JobStatusCard } from './JobStatusCard'
import { PIPELINE_STAGES, type JobStatus, type JobStatusData } from './model'

function fixture(status: JobStatus): JobStatusData {
  return {
    status,
    current_stage: status === 'queued' ? null : 'asr',
    completed_stages: status === 'queued' ? [] : ['preprocess', 'vad'],
    attempt: status === 'retry_scheduled' ? 2 : 1,
    max_attempts: 3,
    error:
      status === 'failed'
        ? new ApiError('AUDIO_INVALID', 'File audio không hợp lệ.')
        : null,
  }
}

describe('JobStatusCard', () => {
  it('shows all six pipeline stages', () => {
    render(<JobStatusCard job={fixture('running')} />)
    const list = screen.getByRole('list')
    expect(within(list).getAllByRole('listitem')).toHaveLength(6)
    expect(PIPELINE_STAGES).toEqual([
      'preprocess',
      'vad',
      'asr',
      'diarize',
      'merge',
      'summarize',
    ])
  })

  it.each([
    ['queued', 'Đang chờ xử lý'],
    ['running', 'Đang xử lý'],
    ['retry_scheduled', 'Đã lên lịch thử lại'],
    ['succeeded', 'Hoàn tất xử lý'],
    ['failed', 'Xử lý thất bại'],
    ['cancelled', 'Đã hủy xử lý'],
  ] as const)('renders job status %s', (status, label) => {
    render(<JobStatusCard job={fixture(status)} />)
    expect(screen.getByRole('status')).toHaveTextContent(label)
  })

  it('shows retry attempt and maximum attempts', () => {
    render(<JobStatusCard job={fixture('retry_scheduled')} />)
    expect(screen.getByText('Lượt thử 2/3')).toBeInTheDocument()
    expect(screen.getByText('Chờ thử lại')).toBeInTheDocument()
  })

  it('shows the localized ApiError message when a job fails', () => {
    render(<JobStatusCard job={fixture('failed')} />)
    expect(screen.getByRole('alert')).toHaveTextContent(
      'File audio không hợp lệ.',
    )
  })
})
