import { useEffect, useRef, useState } from 'react'
import { ArrowLeftIcon } from '@phosphor-icons/react/dist/csr/ArrowLeft'
import { ArrowRightIcon } from '@phosphor-icons/react/dist/csr/ArrowRight'
import { CaretDownIcon } from '@phosphor-icons/react/dist/csr/CaretDown'
import { FileAudioIcon } from '@phosphor-icons/react/dist/csr/FileAudio'
import { MicrophoneIcon } from '@phosphor-icons/react/dist/csr/Microphone'
import { StopIcon } from '@phosphor-icons/react/dist/csr/Stop'
import { UploadSimpleIcon } from '@phosphor-icons/react/dist/csr/UploadSimple'
import { Link, useNavigate } from 'react-router-dom'
import { Topbar } from '../components/Topbar'
import { useObjectUrl } from '../features/audio/useObjectUrl'
import {
  DEFAULT_UPLOAD_CONFIG,
  validateAudio,
} from '../features/audio/validation'
import { useMeetings } from '../features/meetings/DemoStore'
import { formatTime } from '../features/meetings/model'

export function NewMeetingPage() {
  const { add } = useMeetings()
  const navigate = useNavigate()
  const [mode, setMode] = useState<'upload' | 'record'>('upload')
  const [file, setFile] = useState<File>()
  const [duration, setDuration] = useState(0)
  const [title, setTitle] = useState('')
  const [date, setDate] = useState(() => new Date().toLocaleDateString('en-CA'))
  const [consent, setConsent] = useState(false)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const [requesting, setRequesting] = useState(false)
  const [recording, setRecording] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const picker = useRef<HTMLInputElement>(null)
  const recorder = useRef<MediaRecorder | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const timer = useRef<ReturnType<typeof setInterval> | undefined>(undefined)
  const alive = useRef(true)
  const recordStarted = useRef(0)
  const url = useObjectUrl(file)

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
      if (recorder.current?.state === 'recording') {
        recorder.current.onstop = null
        recorder.current.stop()
      }
      stream.current?.getTracks().forEach((t) => t.stop())
      clearInterval(timer.current)
    }
  }, [])
  useEffect(() => {
    if (!recording) return
    const warn = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [recording])

  function choose(selected: File) {
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
  function stop() {
    if (recorder.current?.state === 'recording') recorder.current.stop()
    stream.current?.getTracks().forEach((t) => t.stop())
    clearInterval(timer.current)
    setRecording(false)
  }
  async function start() {
    if (!consent) {
      setError('Hãy xác nhận sự đồng ý trước khi bắt đầu ghi âm.')
      return
    }
    if (
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === 'undefined'
    ) {
      setError(
        'Trình duyệt chưa hỗ trợ ghi âm tại đây. Hãy dùng Chrome/Edge qua localhost hoặc tải file có sẵn.',
      )
      return
    }
    setRequesting(true)
    setError('')
    try {
      const source = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (!alive.current) {
        source.getTracks().forEach((t) => t.stop())
        return
      }
      stream.current = source
      const mime = [
        'audio/webm;codecs=opus',
        'audio/ogg;codecs=opus',
        'audio/mp4',
      ].find((type) => MediaRecorder.isTypeSupported(type))
      const r = new MediaRecorder(source, mime ? { mimeType: mime } : undefined)
      recorder.current = r
      const chunks: Blob[] = []
      let size = 0
      r.ondataavailable = (e) => {
        if (e.data.size) {
          chunks.push(e.data)
          size += e.data.size
          if (
            size >= DEFAULT_UPLOAD_CONFIG.max_upload_mb * 1024 * 1024 &&
            r.state === 'recording'
          )
            r.stop()
        }
      }
      r.onerror = () => {
        source.getTracks().forEach((t) => t.stop())
        clearInterval(timer.current)
        if (alive.current) {
          setError('Ghi âm bị gián đoạn. Hãy thử lại.')
          setRecording(false)
        }
      }
      r.onstop = () => {
        source.getTracks().forEach((t) => t.stop())
        clearInterval(timer.current)
        if (!alive.current) return
        setRecording(false)
        const ext = r.mimeType.includes('mp4')
          ? 'm4a'
          : r.mimeType.includes('ogg')
            ? 'ogg'
            : 'webm'
        const result = new File(chunks, `Ban_ghi_${Date.now()}.${ext}`, {
          type: r.mimeType,
        })
        choose(result)
        setDuration(Math.round((Date.now() - recordStarted.current) / 1000))
      }
      recordStarted.current = Date.now()
      setElapsed(0)
      r.start(1000)
      setRecording(true)
      timer.current = setInterval(() => {
        const seconds = Math.floor((Date.now() - recordStarted.current) / 1000)
        setElapsed(seconds)
        if (seconds >= 3600 && r.state === 'recording') r.stop()
      }, 250)
    } catch {
      stream.current?.getTracks().forEach((t) => t.stop())
      if (alive.current)
        setError(
          'Không truy cập được micro. Kiểm tra quyền micro hoặc chọn tải file audio.',
        )
    } finally {
      if (alive.current) setRequesting(false)
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
            if (!file || !consent || recording || requesting) return
            const invalid = validateAudio(file)
            if (invalid) {
              setError(invalid)
              return
            }
            const id = crypto.randomUUID()
            add(
              {
                id,
                title: title.trim(),
                date,
                time: new Date().toLocaleTimeString('vi-VN', {
                  hour: '2-digit',
                  minute: '2-digit',
                }),
                duration,
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
            navigate(`/meetings/${id}`)
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
                  {formatTime(elapsed)}
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
                    onClick={stop}
                  >
                    <StopIcon weight="fill" />
                    Dừng ghi âm
                  </button>
                ) : (
                  <button
                    className="button primary"
                    type="button"
                    onClick={() => void start()}
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
                    disabled={requesting}
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
              Trong ứng dụng chính thức, transcript có thể được gửi tới dịch vụ
              AI để tạo tóm tắt. Bản xem thử hiện chỉ giữ file trong phiên trình
              duyệt.
            </p>
            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
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
                !file || !consent || !title.trim() || recording || requesting
              }
            >
              Tạo biên bản
              <ArrowRightIcon />
            </button>
          </footer>
        </form>
      </main>
    </>
  )
}
