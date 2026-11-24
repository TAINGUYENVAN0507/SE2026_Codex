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
    // FE-04: giữ dữ liệu khi đổi trang, không mang kết quả của bộ lọc/từ khóa cũ sang.
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey[2] === status && previousQuery?.queryKey[3] === q
        ? previousData
        : undefined,
    refetchInterval: (query) =>
      query.state.data?.items.some(
        (meeting) =>
          meeting.status === 'queued' || meeting.status === 'processing',
      )
        ? 5_000
        : false,
  })
}
