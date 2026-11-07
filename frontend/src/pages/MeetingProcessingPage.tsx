import { ArrowLeftIcon } from '@phosphor-icons/react/dist/csr/ArrowLeft'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getMeeting } from '../api/client'
import { JobStatusCard } from '../features/jobs/JobStatusCard'
import { LoadingSkeleton } from '../components/LoadingSkeleton'

export function MeetingProcessingPage() {
  const { meetingId = '' } = useParams()
  const meeting = useQuery({
    queryKey: ['meeting', meetingId],
    queryFn: () => getMeeting(meetingId),
  })
  const jobId = meeting.data?.latest_job_id || meeting.data?.latest_job?.id
  return (
    <main className="processing-page">
      <Link className="processing-back" to={`/meetings/${meetingId}`}>
        <ArrowLeftIcon size={18} /> Về nội dung cuộc họp
      </Link>
      <header className="processing-intro">
        <h1>Tiến độ xử lý</h1>
        {meeting.data && <p>{meeting.data.title}</p>}
      </header>
      {meeting.isPending ? (
        <LoadingSkeleton kind="transcript" label="Đang tải tiến độ xử lý…" />
      ) : meeting.isError ? (
        <p role="alert">Không tải được cuộc họp. Hãy quay lại và thử lại.</p>
      ) : jobId ? (
        <JobStatusCard jobId={jobId} />
      ) : (
        <p role="status">Cuộc họp chưa có yêu cầu xử lý.</p>
      )}
      <p className="processing-help">
        Bạn có thể rời trang này. Hệ thống tiếp tục xử lý và lưu kết quả; phần
        transcript đã có vẫn đọc và chỉnh sửa được.
      </p>
      <Link className="button primary" to={`/meetings/${meetingId}`}>
        Mở nội dung cuộc họp
      </Link>
    </main>
  )
}
