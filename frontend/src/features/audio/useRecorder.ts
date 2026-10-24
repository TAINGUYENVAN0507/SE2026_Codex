import { useCallback, useEffect, useRef, useState } from 'react'
import { DEFAULT_UPLOAD_CONFIG } from './validation'

export type RecorderStatus =
  | 'idle'
  | 'requesting'
  | 'recording'
  | 'stopped'
  | 'uploading'
  | 'done'
  | 'denied'
  | 'error'

const MAX_RECORD_SECONDS = 3600
const MIME_TYPES = [
  'audio/webm;codecs=opus',
  'audio/ogg;codecs=opus',
  'audio/mp4',
]

export function useRecorder(
  onRecorded: (file: File, duration: number) => void,
) {
  const [status, setStatus] = useState<RecorderStatus>('idle')
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState('')
  const recorder = useRef<MediaRecorder | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const timer = useRef<ReturnType<typeof setInterval> | undefined>(undefined)
  const started = useRef(0)
  const alive = useRef(true)
  const requestGeneration = useRef(0)
  const onRecordedRef = useRef(onRecorded)

  useEffect(() => {
    onRecordedRef.current = onRecorded
  }, [onRecorded])

  const release = useCallback(() => {
    stream.current?.getTracks().forEach((track) => track.stop())
    stream.current = null
    clearInterval(timer.current)
  }, [])

  const cancel = useCallback(() => {
    requestGeneration.current += 1
    if (recorder.current?.state === 'recording') {
      recorder.current.onstop = null
      recorder.current.stop()
    }
    release()
    if (alive.current) setStatus('idle')
  }, [release])

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
      requestGeneration.current += 1
      if (recorder.current?.state === 'recording') {
        recorder.current.onstop = null
        recorder.current.stop()
      }
      release()
    }
  }, [release])

  async function start(consent: boolean) {
    if (!consent) {
      setError('Hãy xác nhận sự đồng ý trước khi bắt đầu ghi âm.')
      return
    }
    if (
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === 'undefined'
    ) {
      setStatus('error')
      setError(
        'Trình duyệt chưa hỗ trợ ghi âm. Hãy dùng Chrome/Edge qua localhost hoặc tải file có sẵn.',
      )
      return
    }
    if (status === 'requesting' || status === 'recording') return
    setStatus('requesting')
    setError('')
    const generation = ++requestGeneration.current
    try {
      const source = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (!alive.current || generation !== requestGeneration.current) {
        source.getTracks().forEach((track) => track.stop())
        return
      }
      stream.current = source
      const mime = MIME_TYPES.find((type) =>
        MediaRecorder.isTypeSupported(type),
      )
      const instance = new MediaRecorder(
        source,
        mime ? { mimeType: mime } : undefined,
      )
      recorder.current = instance
      const chunks: Blob[] = []
      let size = 0
      instance.ondataavailable = (event) => {
        if (!event.data.size) return
        chunks.push(event.data)
        size += event.data.size
        if (
          size >= DEFAULT_UPLOAD_CONFIG.max_upload_mb * 1024 * 1024 &&
          instance.state === 'recording'
        )
          instance.stop()
      }
      instance.onerror = () => {
        instance.onstop = null
        release()
        if (alive.current) {
          setStatus('error')
          setError('Ghi âm bị gián đoạn. Hãy thử lại.')
        }
      }
      instance.onstop = () => {
        release()
        if (!alive.current) return
        setStatus('stopped')
        const extension = instance.mimeType.includes('mp4')
          ? 'm4a'
          : instance.mimeType.includes('ogg')
            ? 'ogg'
            : 'webm'
        const file = new File(chunks, `Ban_ghi_${Date.now()}.${extension}`, {
          type: instance.mimeType,
        })
        onRecordedRef.current(
          file,
          Math.round((Date.now() - started.current) / 1000),
        )
      }
      started.current = Date.now()
      setElapsed(0)
      instance.start(1000)
      setStatus('recording')
      timer.current = setInterval(() => {
        const seconds = Math.floor((Date.now() - started.current) / 1000)
        setElapsed(seconds)
        if (seconds >= MAX_RECORD_SECONDS && instance.state === 'recording')
          instance.stop()
      }, 250)
    } catch {
      release()
      if (alive.current) {
        setStatus('denied')
        setError(
          'Không truy cập được micro. Kiểm tra quyền micro hoặc chọn tải file audio.',
        )
      }
    }
  }

  function stop() {
    if (recorder.current?.state === 'recording') recorder.current.stop()
    release()
  }

  return {
    status,
    elapsed,
    error,
    start,
    stop,
    cancel,
    startUpload: () => setStatus('uploading'),
    finishUpload: () => setStatus('done'),
    cancelUpload: () => setStatus('stopped'),
  }
}
