import { useQuery } from '@tanstack/react-query'
import { getJob, type Job } from '../../api/client'

const POLL_INTERVAL_MS = 2_000
const ACTIVE_STATUSES: ReadonlySet<Job['status']> = new Set([
  'queued',
  'running',
  'retry_scheduled',
])

export function useJobQuery(jobId: string) {
  return useQuery({
    queryKey: ['job', jobId],
    queryFn: () => getJob(jobId),
    enabled: Boolean(jobId),
    refetchInterval: (query) =>
      query.state.data && ACTIVE_STATUSES.has(query.state.data.status)
        ? POLL_INTERVAL_MS
        : false,
  })
}
