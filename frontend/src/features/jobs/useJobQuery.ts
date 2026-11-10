import { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getJob, type Job } from '../../api/client'
import { ApiError } from '../../api/errors'

const POLL_INTERVAL_MS = 2_000
const MAX_BACKOFF_MS = 10_000
const ACTIVE_STATUSES: ReadonlySet<Job['status']> = new Set([
  'queued',
  'running',
  'retry_scheduled',
])

function transient(error: unknown) {
  return (
    error instanceof ApiError &&
    (error.status === 503 || error.code === 'NETWORK_ERROR')
  )
}

export function useJobQuery(jobId: string) {
  const failures = useRef({ id: jobId, count: 0 })
  const [pollDelayMs, setPollDelayMs] = useState(POLL_INTERVAL_MS)
  const query = useQuery({
    queryKey: ['job', jobId],
    queryFn: async ({ signal }) => {
      if (failures.current.id !== jobId)
        failures.current = { id: jobId, count: 0 }
      try {
        const result = await getJob(jobId, signal)
        failures.current.count = 0
        setPollDelayMs(POLL_INTERVAL_MS)
        return result
      } catch (error) {
        if (transient(error)) {
          failures.current.count++
          const wait =
            (error as ApiError).retryAfterMs ??
            POLL_INTERVAL_MS * 2 ** Math.min(failures.current.count, 3)
          setPollDelayMs(Math.min(MAX_BACKOFF_MS, Math.max(1_000, wait)))
        }
        throw error
      }
    },
    enabled: Boolean(jobId),
    // Chỉ một lịch poll điều khiển retry; không cộng thêm retry mặc định của Query.
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchInterval: (current) => {
      const data = current.state.data
      if (data && !ACTIVE_STATUSES.has(data.status)) return false
      if (current.state.error)
        return transient(current.state.error) ? pollDelayMs : false
      return data ? POLL_INTERVAL_MS : false
    },
  })
  return { ...query, pollDelayMs }
}
