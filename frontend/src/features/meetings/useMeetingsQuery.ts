import { useQuery } from '@tanstack/react-query'
import { listMeetings, type MeetingDetail } from '../../api/client'

export function useMeetingsQuery({
  page,
  status,
  q = '',
}: {
  page: number
  status?: MeetingDetail['status']
  q?: string
}) {
  return useQuery({
    queryKey: ['meetings', page, status, q],
    queryFn: () => listMeetings(page, status, q),
    refetchInterval: (query) =>
      query.state.data?.items.some(
        (meeting) =>
          meeting.status === 'queued' || meeting.status === 'processing',
      )
        ? 5_000
        : false,
  })
}
