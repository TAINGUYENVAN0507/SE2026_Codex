import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { Job } from '../../api/client'
import { JobTimes } from './JobTimes'
import job from '../../../../contracts/fixtures/api/job_retry_scheduled.json'

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})
const base = {
  ...job,
  created_at: '2026-11-10T00:00:00Z',
  started_at: null,
  finished_at: null,
} as Job

it('VT-018: queued counts wait from created_at using the live clock', async () => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-11-10T00:01:00Z'))
  render(<JobTimes job={{ ...base, status: 'queued' }} />)
  expect(screen.getByText('Đã chờ 01:00')).toBeInTheDocument()
  expect(screen.queryByText(/Đã chạy/)).not.toBeInTheDocument()
  await act(async () => vi.advanceTimersByTimeAsync(1000))
  expect(screen.getByText('Đã chờ 01:01')).toBeInTheDocument()
})

it('VT-018: running freezes queue wait and exposes local start time', () => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-11-10T00:02:00Z'))
  render(
    <JobTimes
      job={{ ...base, status: 'running', started_at: '2026-11-10T00:00:30Z' }}
    />,
  )
  expect(screen.getByText('Đã chờ 00:30')).toBeInTheDocument()
  expect(screen.getByText('Đã chạy 01:30')).toBeInTheDocument()
  const time = screen.getByLabelText('Giờ bắt đầu')
  expect(time).toHaveAttribute('datetime', '2026-11-10T00:00:30Z')
  expect(time.textContent).toBe(
    new Intl.DateTimeFormat('vi-VN', {
      dateStyle: 'short',
      timeStyle: 'medium',
    }).format(new Date('2026-11-10T00:00:30Z')),
  )
})

it('VT-018: completed job stops both clocks at server timestamps', async () => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-11-10T00:05:00Z'))
  render(
    <JobTimes
      job={{
        ...base,
        status: 'succeeded',
        started_at: '2026-11-10T00:00:10Z',
        finished_at: '2026-11-10T00:00:42Z',
      }}
    />,
  )
  expect(screen.getByText('Đã chờ 00:10')).toBeInTheDocument()
  expect(screen.getByText('Đã chạy 00:32')).toBeInTheDocument()
  expect(screen.getByLabelText('Giờ hoàn thành')).toHaveAttribute(
    'datetime',
    '2026-11-10T00:00:42Z',
  )
  await act(async () => vi.advanceTimersByTimeAsync(60_000))
  expect(screen.getByText('Đã chạy 00:32')).toBeInTheDocument()
})

it('VT-018: missing or invalid timestamps never show NaN or Invalid Date', () => {
  const { container } = render(
    <JobTimes
      job={{
        ...base,
        status: 'succeeded',
        created_at: 'invalid',
        started_at: 'bad',
        finished_at: null,
      }}
    />,
  )
  expect(container.textContent).not.toMatch(/NaN|Invalid Date|Đã chờ|Đã chạy/)
  expect(screen.queryByLabelText('Giờ bắt đầu')).not.toBeInTheDocument()
})
