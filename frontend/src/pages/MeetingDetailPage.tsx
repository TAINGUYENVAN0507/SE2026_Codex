import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeftIcon } from '@phosphor-icons/react/dist/csr/ArrowLeft'
import { CaretDownIcon } from '@phosphor-icons/react/dist/csr/CaretDown'
import { CheckIcon } from '@phosphor-icons/react/dist/csr/Check'
import { ClockIcon } from '@phosphor-icons/react/dist/csr/Clock'
import { DownloadSimpleIcon } from '@phosphor-icons/react/dist/csr/DownloadSimple'
import { PencilSimpleIcon } from '@phosphor-icons/react/dist/csr/PencilSimple'
import { UsersIcon } from '@phosphor-icons/react/dist/csr/Users'
import { Link, useParams } from 'react-router-dom'
import { AudioPlayer, type PlayerHandle } from '../features/audio/AudioPlayer'
import { validateAudio } from '../features/audio/validation'
import { useMeetings } from '../features/meetings/DemoStore'
import {
  exportMeeting,
  formatDate,
  type Meeting,
} from '../features/meetings/model'
import { Transcript } from '../features/meetings/Transcript'
import { NotesPanel } from '../features/meetings/NotesPanel'

export function MeetingDetailPage() {
  const { meetingId } = useParams()
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
}: {
  meeting: Meeting
  file?: File
  onUpdate: (f: (m: Meeting) => Meeting) => void
}) {
  const [localFile, setLocalFile] = useState<File | undefined>(file)
  const [position, setPosition] = useState(file ? 0 : 255)
  const [side, setSide] = useState<'summary' | 'tasks'>('summary')
  const [mobile, setMobile] = useState<'transcript' | 'summary' | 'tasks'>(
    'transcript',
  )
  const [exportOpen, setExportOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [rename, setRename] = useState(false)
  const [title, setTitle] = useState(meeting.title)
  const player = useRef<PlayerHandle>(null)
  const dropdown = useRef<HTMLDivElement>(null)
  const onPosition = useCallback((value: number) => setPosition(value), [])
  const active = meeting.segments.find(
    (s) => position >= s.start && position < s.end,
  )
  const name = meeting.speakers.find((s) => s.id === active?.speakerId)?.name
  useEffect(() => {
    const close = (e: PointerEvent) => {
      if (!dropdown.current?.contains(e.target as Node)) setExportOpen(false)
    }
    const escape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setExportOpen(false)
    }
    document.addEventListener('pointerdown', close)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', close)
      document.removeEventListener('keydown', escape)
    }
  }, [])
  const seek = (seconds: number) => {
    player.current?.seek(seconds)
    setMobile('transcript')
    const seg = meeting.segments.find((s) => s.start === seconds)
    if (seg)
      requestAnimationFrame(() =>
        document
          .getElementById(`segment-${seg.id}`)
          ?.scrollIntoView({ block: 'center', behavior: 'smooth' }),
      )
  }
  function download(format: 'txt' | 'md' | 'json') {
    const url = URL.createObjectURL(
      new Blob([exportMeeting(meeting, format)], {
        type:
          format === 'json'
            ? 'application/json;charset=utf-8'
            : 'text/plain;charset=utf-8',
      }),
    )
    const a = document.createElement('a')
    a.href = url
    a.download = `bien-ban-${meeting.id}.${format}`
    a.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    setExportOpen(false)
    setMessage('Đã xuất bản chỉnh sửa hiện tại.')
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
        <div className="dropdown" ref={dropdown}>
          <button
            className="button primary"
            aria-expanded={exportOpen}
            aria-controls="export-menu"
            onClick={() => setExportOpen((v) => !v)}
            disabled={!meeting.segments.length}
          >
            <DownloadSimpleIcon />
            Xuất biên bản
            <CaretDownIcon size={12} />
          </button>
          {exportOpen && (
            <div className="export-menu" id="export-menu">
              <span>BẢN ĐÃ CHỈNH SỬA</span>
              {(['txt', 'md', 'json'] as const).map((f) => (
                <button key={f} onClick={() => download(f)}>
                  {
                    {
                      txt: 'Văn bản (.txt)',
                      md: 'Markdown (.md)',
                      json: 'Dữ liệu (.json)',
                    }[f]
                  }
                </button>
              ))}
            </div>
          )}
        </div>
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
        {(['transcript', 'summary', 'tasks'] as const).map((t) => (
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
              }[t]
            }
          </button>
        ))}
      </nav>
      <div className="meeting-workspace" data-mobile={mobile}>
        <Transcript
          meeting={meeting}
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
        />
      </div>
    </main>
  )
}
