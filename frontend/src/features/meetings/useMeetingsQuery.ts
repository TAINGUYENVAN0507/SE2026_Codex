import { useQuery } from '@tanstack/react-query'
import { listMeetings, type MeetingDetail } from '../../api/client'

export function useMeetingsQuery({
  page,
  status,
}: {
  page: number
  status?: MeetingDetail['status']
}) {
  return useQuery({
    queryKey: ['meetings', page, status],
    queryFn: () => listMeetings(page, status),
    refetchInterval: (query) =>
      query.state.data?.items.some(
        (meeting) =>
          meeting.status === 'queued' || meeting.status === 'processing',
      )
        ? 5_000
        : false,
  })
}
