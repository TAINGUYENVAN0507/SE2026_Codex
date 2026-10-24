import { useEffect, useRef, useState } from 'react'
import { ArrowLeftIcon } from '@phosphor-icons/react/dist/csr/ArrowLeft'
import { ArrowRightIcon } from '@phosphor-icons/react/dist/csr/ArrowRight'
import { CaretDownIcon } from '@phosphor-icons/react/dist/csr/CaretDown'
import { FileAudioIcon } from '@phosphor-icons/react/dist/csr/FileAudio'
import { MicrophoneIcon } from '@phosphor-icons/react/dist/csr/Microphone'
import { StopIcon } from '@phosphor-icons/react/dist/csr/Stop'
import { UploadSimpleIcon } from '@phosphor-icons/react/dist/csr/UploadSimple'
import { Link, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { Topbar } from '../components/Topbar'
import { useObjectUrl } from '../features/audio/useObjectUrl'
import { useIdempotencyKey } from '../features/audio/useIdempotencyKey'
import { useRecorder } from '../features/audio/useRecorder'
import { uploadMeeting } from '../features/audio/uploadMeeting'
import { ApiError } from '../api/errors'
import {
  DEFAULT_UPLOAD_CONFIG,
  validateAudio,
} from '../features/audio/validation'
import { useMeetings } from '../features/meetings/DemoStore'
import { formatTime } from '../features/meetings/model'

export function NewMeetingPage() {
  const { add } = useMeetings()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<'upload' | 'record'>('upload')
  const [file, setFile] = useState<File>()
  const [duration, setDuration] = useState(0)
  const [title, setTitle] = useState('')
  const [date, setDate] = useState(() => new Date().toLocaleDateString('en-CA'))
  const [consent, setConsent] = useState(false)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const activeUpload = useRef<ReturnType<typeof uploadMeeting> | null>(null)
  const picker = useRef<HTMLInputElement>(null)
  const alive = useRef(true)
  const url = useObjectUrl(file)
  const idempotencyKey = useIdempotencyKey(file ?? null)
  const record = useRecorder((recordedFile, seconds) => {
    choose(recordedFile)
    setDuration(seconds)
  })
  const recording = record.status === 'recording'
  const requesting = record.status === 'requesting'

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
      activeUpload.current?.abort()
    }
  }, [])
  useEffect(() => {
    if (!recording) return
    const warn = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [recording])

  function choose(selected: File) {
    if (uploading) return
    const invalid = validateAudio(selected)
    if (invalid) {
      setError(invalid)
      return
    }
    setFile(selected)
    setDuration(0)
    setError('')
    if (!title.trim())
      setTitle(selected.name.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' '))
  }
  async function submit() {
    if (
      !file ||
      !consent ||
      !idempotencyKey ||
      recording ||
      requesting ||
      uploading
    )
      return
    const invalid = validateAudio(file)
    if (invalid) {
      setError(invalid)
      return
    }
    setError('')
    setProgress(0)
    setUploading(true)
    if (mode === 'record') record.startUpload()
    const upload = uploadMeeting(
      file,
      {
        title: title.trim(),
        meetingDate: date,
        source: mode === 'record' ? 'recording' : 'upload',
      },
      idempotencyKey,
      setProgress,
    )
    activeUpload.current = upload
    try {
      const result = await upload.promise
      add(
        {
          id: result.meeting.id,
          title: result.meeting.title,
          date: result.meeting.meeting_date || date,
          time: new Date().toLocaleTimeString('vi-VN', {
            hour: '2-digit',
            minute: '2-digit',
          }),
          duration: result.meeting.duration_sec || duration,
          status: 'pending',
          speakers: [],
          segments: [],
          overview: '',
          points: [],
          decisions: [],
          tasks: [],
          fileName: file.name,
        },
        file,
      )
      void queryClient.invalidateQueries({ queryKey: ['meetings'] })
      if (mode === 'record') record.finishUpload()
      navigate(`/meetings/${result.meeting.id}`)
    } catch (cause) {
      if (cause instanceof ApiError && cause.code !== 'UPLOAD_CANCELLED')
        setError(cause.message)
      else if (!(cause instanceof ApiError))
        setError('Không thể tải file lên. Hãy thử lại.')
      if (mode === 'record') record.cancelUpload()
    } finally {
      activeUpload.current = null
      if (alive.current) setUploading(false)
    }
  }
  return (
    <>
      <Topbar />
      <main className="new-page">
        <Link to="/meetings" className="back-link">
          <ArrowLeftIcon />
          Cuộc họp
        </Link>
        <h1>Tạo cuộc họp mới</h1>
        <p className="page-description">
          Tải audio hoặc ghi âm để bắt đầu biên bản.
        </p>
        <form
          className="create-card"
          onSubmit={(e) => {
            e.preventDefault()
            void submit()
          }}
        >
          <div className="create-source">
            <div className="source-tabs" role="group" aria-label="Nguồn audio">
              <button
                type="button"
                aria-pressed={mode === 'upload'}
                className={mode === 'upload' ? 'selected' : ''}
                onClick={() => setMode('upload')}
                disabled={recording || requesting}
              >
                <UploadSimpleIcon />
                Tải file audio
              </button>
              <button
                type="button"
                aria-pressed={mode === 'record'}
                className={mode === 'record' ? 'selected' : ''}
                onClick={() => setMode('record')}
                disabled={recording || requesting}
              >
                <MicrophoneIcon />
                Ghi âm
              </button>
            </div>
            <input
              type="file"
              hidden
              ref={picker}
              disabled={uploading}
              accept={DEFAULT_UPLOAD_CONFIG.allowed_extensions
                .map((extension) => `.${extension.replace(/^\./, '')}`)
                .join(',')}
              aria-label="Chọn file audio"
              onChange={(e) => {
                const selected = e.target.files?.[0]
                if (selected) choose(selected)
                e.target.value = ''
              }}
            />
            {mode === 'record' && (
              <section
                className={`recorder-panel ${recording ? 'recording' : ''}`}
                aria-label="Ghi âm"
              >
                <span className="record-symbol">
                  <MicrophoneIcon size={27} />
                </span>
                <p className="recorder-time mono" aria-live="off">
                  {formatTime(record.elapsed)}
                </p>
                <p className="recorder-status" role="status">
                  {recording
                    ? 'Đang ghi âm · tối đa 60 phút'
                    : requesting
                      ? 'Đang chờ quyền micro…'
                      : 'Xác nhận sự đồng ý rồi bấm bắt đầu.'}
                </p>
                {recording ? (
                  <button
                    className="button primary"
                    type="button"
                    onClick={record.stop}
                  >
                    <StopIcon weight="fill" />
                    Dừng ghi âm
                  </button>
                ) : (
                  <button
                    className="button primary"
                    type="button"
                    onClick={() => void record.start(consent)}
                    disabled={!consent || requesting}
                  >
                    <MicrophoneIcon />
                    {file ? 'Ghi lại' : 'Bắt đầu ghi âm'}
                  </button>
                )}
              </section>
            )}
            {file && !recording ? (
              <div className="selected-audio">
                <div className="selected-file-heading">
                  <span className="file-audio-icon">
                    <FileAudioIcon size={26} />
                  </span>
                  <div>
                    <strong>{file.name}</strong>
                    <p>
                      {(file.size / 1024 / 1024).toFixed(1)} MB{' '}
                      {duration > 0 && `· ${formatTime(duration)}`}
                    </p>
                  </div>
                  <button
                    className="button secondary small"
                    type="button"
                    onClick={() => picker.current?.click()}
                    disabled={requesting || uploading}
                  >
                    Đổi file
                  </button>
                </div>
                <audio
                  key={url}
                  src={url}
                  controls
                  preload="metadata"
                  onLoadedMetadata={(e) => {
                    if (Number.isFinite(e.currentTarget.duration))
                      setDuration(e.currentTarget.duration)
                  }}
                  onError={() =>
                    setError(
                      'Không thể nghe thử file này trên trình duyệt. Hãy thử MP3 hoặc WAV.',
                    )
                  }
                />
                <p className="local-audio-note">
                  Nghe thử trên máy · chưa tải lên
                </p>
              </div>
            ) : (
              mode === 'upload' && (
                <div
                  className={`dropzone ${dragging ? 'dragging' : ''}`}
                  onDragOver={(e) => {
                    e.preventDefault()
                    setDragging(true)
                  }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={(e) => {
                    e.preventDefault()
                    setDragging(false)
                    const selected = e.dataTransfer.files[0]
                    if (selected) choose(selected)
                  }}
                >
                  <span className="upload-symbol">
                    <UploadSimpleIcon size={27} />
                  </span>
                  <h2>Kéo file audio vào đây</h2>
                  <p>
                    {DEFAULT_UPLOAD_CONFIG.allowed_extensions
                      .map((extension) => extension.toUpperCase())
                      .join(', ')}{' '}
                    · tối đa {DEFAULT_UPLOAD_CONFIG.max_upload_mb} MB
                  </p>
                  <button
                    className="button secondary"
                    type="button"
                    onClick={() => picker.current?.click()}
                  >
                    Chọn file trên máy
                  </button>
                </div>
              )
            )}
          </div>
          <div className="create-settings">
            <label className="field">
              <span>Tên cuộc họp</span>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Ví dụ: Họp kế hoạch sprint 42"
                required
                maxLength={200}
              />
            </label>
            <details className="advanced-options">
              <summary>
                Tùy chọn cuộc họp
                <CaretDownIcon size={16} />
              </summary>
              <div className="advanced-fields">
                <label className="field">
                  <span>Ngày họp</span>
                  <input
                    type="date"
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                    required
                  />
                </label>
                <div className="field">
                  <span>Số người nói dự kiến</span>
                  <select aria-label="Số người nói dự kiến" disabled>
                    <option>Tự động (chờ kết nối API)</option>
                  </select>
                </div>
              </div>
            </details>
            <label className="consent-check">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                required
                disabled={recording || requesting}
              />
              <span>
                Tôi xác nhận đã có sự đồng ý cần thiết của người tham gia trước
                khi tải bản ghi.
              </span>
            </label>
            <p className="privacy-description">
              Khi tạo cuộc họp, file audio sẽ được gửi tới API để xử lý. Trong
              chế độ API mô phỏng, dữ liệu không được lưu lên máy chủ.
            </p>
            {(error || record.error) && (
              <p className="form-error" role="alert">
                {error || record.error}
              </p>
            )}
            {uploading && (
              <div role="status" aria-label="Tiến độ tải lên">
                Đang tải lên: {progress}%
              </div>
            )}
          </div>
          <footer className="create-footer">
            <Link className="button secondary" to="/meetings">
              Hủy
            </Link>
            <button
              className="button primary"
              type="submit"
              disabled={
                !file ||
                !consent ||
                !title.trim() ||
                recording ||
                requesting ||
                uploading
              }
            >
              Tạo biên bản
              <ArrowRightIcon />
            </button>
            {uploading && (
              <button
                className="button secondary"
                type="button"
                onClick={() => activeUpload.current?.abort()}
              >
                Hủy tải lên
              </button>
            )}
          </footer>
        </form>
      </main>
    </>
  )
}
