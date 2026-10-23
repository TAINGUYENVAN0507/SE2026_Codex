import { useQuery } from '@tanstack/react-query'
import { getTranscript } from '../../api/client'

export function useTranscriptQuery(meetingId: string) {
  return useQuery({
    queryKey: ['transcript', meetingId],
    queryFn: () => getTranscript(meetingId),
    enabled: Boolean(meetingId),
    refetchInterval: (query) =>
      query.state.data?.status === 'pending' ? 5_000 : false,
  })
}
