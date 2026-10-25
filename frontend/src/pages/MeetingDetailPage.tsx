import { useCallback, useMemo, useRef, useState } from 'react'
import { ArrowLeftIcon } from '@phosphor-icons/react/dist/csr/ArrowLeft'
import { CheckIcon } from '@phosphor-icons/react/dist/csr/Check'
import { ClockIcon } from '@phosphor-icons/react/dist/csr/Clock'
import { PencilSimpleIcon } from '@phosphor-icons/react/dist/csr/PencilSimple'
import { UsersIcon } from '@phosphor-icons/react/dist/csr/Users'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ApiError } from '../api/errors'
import { getMeeting } from '../api/client'
import { AudioPlayer, type PlayerHandle } from '../features/audio/AudioPlayer'
import { validateAudio } from '../features/audio/validation'
import { useMeetings } from '../features/meetings/DemoStore'
import { formatDate, type Meeting } from '../features/meetings/model'
import { ExportMenu } from '../features/export/ExportMenu'
import { Transcript } from '../features/meetings/Transcript'
import { NotesPanel, type NotesTab } from '../features/meetings/NotesPanel'
import { useActiveSegment } from '../features/meetings/useActiveSegment'
import { useTranscriptQuery } from '../features/meetings/useTranscriptQuery'
import { apiMeetingToView } from '../features/meetings/apiModel'
import { DEMO_ID } from '../features/meetings/model'
import { NotFoundPage } from './NotFoundPage'
import { LoadingSkeleton } from '../components/LoadingSkeleton'

export function MeetingDetailPage() {
  const { meetingId } = useParams()
  if (
    meetingId !== DEMO_ID &&
    !/^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(meetingId || '')
  )
    return <NotFoundPage meeting />
  if (meetingId && meetingId !== DEMO_ID)
    return <RemoteMeetingDetail meetingId={meetingId} />
  return <DemoMeetingDetail meetingId={meetingId} />
}

function RemoteMeetingDetail({ meetingId }: { meetingId: string }) {
  const meetingQuery = useQuery({
    queryKey: ['meeting', meetingId],
    queryFn: () => getMeeting(meetingId),
  })
  const transcriptQuery = useTranscriptQuery(meetingId)
  if (meetingQuery.isPending || transcriptQuery.isPending)
    return (
      <main className="loading-detail">
        <LoadingSkeleton
          kind="transcript"
          label="Đang tải cuộc họp và transcript…"
        />
      </main>
    )
  if (meetingQuery.isError || transcriptQuery.isError) {
    const error = meetingQuery.error || transcriptQuery.error
    if (
      error instanceof ApiError &&
      (error.status === 404 || error.code === 'MEETING_NOT_FOUND')
    )
      return <NotFoundPage meeting />
    return (
      <main className="missing-meeting" role="alert">
        <h1>Không tải được cuộc họp</h1>
        <p>
          {error instanceof ApiError ? error.message : 'Hãy thử tải lại trang.'}
        </p>
        <Link to="/meetings">Về danh sách cuộc họp</Link>
      </main>
    )
  }
  return (
    <RemoteMeetingContent
      key={`${meetingId}-${transcriptQuery.data.status}`}
      meeting={apiMeetingToView(meetingQuery.data, transcriptQuery.data)}
      pending={transcriptQuery.data.status === 'pending'}
      ready={transcriptQuery.data.status === 'ready'}
    />
  )
}

function RemoteMeetingContent({
  meeting: initial,
  pending,
  ready,
}: {
  meeting: Meeting
  pending: boolean
  ready: boolean
}) {
  const [meeting, setMeeting] = useState(initial)
  const { files } = useMeetings()
  return (
    <Detail
      meeting={meeting}
      file={files[meeting.id]}
      pending={pending}
      transcriptReady={ready}
      onUpdate={(transform) => setMeeting((current) => transform(current))}
      remote
    />
  )
}

function DemoMeetingDetail({ meetingId }: { meetingId?: string }) {
  const { meetings, files, update } = useMeetings()
  const meeting = meetings.find((m) => m.id === meetingId)
  if (!meeting)
    return (
      <main className="missing-meeting">
        <h1>Không tìm thấy cuộc họp</h1>
        <p>Cuộc họp chưa tồn tại hoặc dữ liệu phiên trước đã được làm mới.</p>
        <Link className="button primary" to="/meetings">
          Về danh sách cuộc họp
        </Link>
      </main>
    )
  return (
    <Detail
      key={meeting.id}
      meeting={meeting}
      file={files[meeting.id]}
      onUpdate={(f) => update(meeting.id, f)}
    />
  )
}

function Detail({
  meeting,
  file,
  onUpdate,
  pending = false,
  remote = false,
  transcriptReady = meeting.status === 'ready',
}: {
  meeting: Meeting
  file?: File
  onUpdate: (f: (m: Meeting) => Meeting) => void
  pending?: boolean
  remote?: boolean
  transcriptReady?: boolean
}) {
  const [localFile, setLocalFile] = useState<File | undefined>(file)
  const [position, setPosition] = useState(
    file ? 0 : Math.max(0, Math.min(255, meeting.duration)),
  )
  const [side, setSide] = useState<NotesTab>('summary')
  const [mobile, setMobile] = useState<'transcript' | NotesTab>('transcript')
  const [message, setMessage] = useState('')
  const [rename, setRename] = useState(false)
  const [title, setTitle] = useState(meeting.title)
  const player = useRef<PlayerHandle>(null)
  const onPosition = useCallback((value: number) => setPosition(value), [])
  const timedSegments = useMemo(
    () =>
      meeting.segments.map((segment) => ({
        ...segment,
        start_sec: segment.start,
        end_sec: segment.end,
      })),
    [meeting.segments],
  )
  const active = useActiveSegment(timedSegments, position)
  const name = meeting.speakers.find((s) => s.id === active?.speakerId)?.name
  const seek = (seconds: number) => {
    player.current?.seek(seconds)
    setMobile('transcript')
  }
  return (
    <main className="detail-page">
      <header className="detail-header">
        <div className="breadcrumbs">
          <Link to="/meetings">
            <ArrowLeftIcon />
            Cuộc họp
          </Link>
          <span>/</span>
          <strong>{meeting.title}</strong>
        </div>
        <div className="meeting-intro">
          <div className="meeting-title-row">
            {rename ? (
              <form
                className="rename-form"
                onSubmit={(e) => {
                  e.preventDefault()
                  if (title.trim()) {
                    onUpdate((m) => ({ ...m, title: title.trim() }))
                    setRename(false)
                  }
                }}
              >
                <input
                  aria-label="Tên cuộc họp"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  maxLength={200}
                  autoFocus
                  required
                  onKeyDown={(e) => {
                    if (e.key === 'Escape') setRename(false)
                  }}
                />
                <button className="icon-button" aria-label="Lưu tên cuộc họp">
                  <CheckIcon />
                </button>
                <button
                  className="button quiet small"
                  type="button"
                  onClick={() => setRename(false)}
                >
                  Hủy
                </button>
              </form>
            ) : (
              <div className="editable-title">
                <h1>{meeting.title}</h1>
                <button
                  className="icon-button"
                  aria-label="Đổi tên cuộc họp"
                  onClick={() => {
                    setTitle(meeting.title)
                    setRename(true)
                  }}
                >
                  <PencilSimpleIcon size={17} />
                </button>
              </div>
            )}
            <span className={`status-label ${meeting.status}`}>
              <i />
              {
                {
                  ready: 'Đã xử lý',
                  processing: 'Đang xử lý',
                  failed: 'Lỗi âm thanh',
                  pending: 'Chờ kết nối xử lý',
                }[meeting.status]
              }
            </span>
          </div>
          <div className="meeting-meta">
            <span>
              <ClockIcon />
              {formatDate(meeting.date)} · {meeting.time}
            </span>
            <span>{Math.floor(meeting.duration / 60)} phút</span>
            <span>
              <UsersIcon />
              {meeting.speakers.length || 'Chưa xác định'} người nói
            </span>
            <span>Tiếng Việt</span>
          </div>
        </div>
        <ExportMenu meetingId={meeting.id} ready={transcriptReady} />
      </header>
      <AudioPlayer
        key={`${localFile?.name || 'demo'}-${localFile?.lastModified || 0}`}
        file={localFile}
        duration={meeting.duration}
        speaker={name}
        onPosition={onPosition}
        ref={player}
        onFile={(f) => {
          const error = validateAudio(f)
          if (error) setMessage(error)
          else {
            setLocalFile(f)
            setMessage('Đã chọn audio. Transcript vẫn là dữ liệu mẫu.')
          }
        }}
      />
      {message && (
        <div className="detail-notice" role="status">
          {message}
          <button className="button quiet small" onClick={() => setMessage('')}>
            Đóng
          </button>
        </div>
      )}
      {meeting.status !== 'ready' && (
        <div className="detail-notice" role="status">
          {
            {
              pending:
                'Bản ghi đã được giữ trong phiên này. Hệ thống chưa kết nối backend để xử lý AI.',
              processing:
                'Trạng thái xử lý minh họa. Job thật sẽ được kết nối khi backend sẵn sàng.',
              failed:
                'Bản ghi mẫu gặp lỗi âm thanh. Bạn có thể tạo cuộc họp mới bằng một file khác.',
              ready: '',
            }[meeting.status]
          }
        </div>
      )}
      <nav className="mobile-detail-tabs" aria-label="Nội dung cuộc họp">
        {(['transcript', 'summary', 'tasks', 'history'] as const).map((t) => (
          <button
            key={t}
            className={mobile === t ? 'selected' : ''}
            aria-pressed={mobile === t}
            onClick={() => {
              setMobile(t)
              if (t !== 'transcript') setSide(t)
            }}
          >
            {
              {
                transcript: 'Transcript',
                summary: 'Tóm tắt',
                tasks: 'Công việc',
                history: 'Lịch sử',
              }[t]
            }
          </button>
        ))}
      </nav>
      <div className="meeting-workspace" data-mobile={mobile}>
        <Transcript
          meeting={meeting}
          pending={pending}
          position={position}
          onSeek={seek}
          onUpdate={onUpdate}
        />
        <NotesPanel
          meeting={meeting}
          tab={side}
          setTab={setSide}
          onSeek={seek}
          onUpdate={onUpdate}
          remote={remote}
        />
      </div>
    </main>
  )
}
