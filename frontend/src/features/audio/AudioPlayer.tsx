import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react'
import { PauseIcon } from '@phosphor-icons/react/dist/csr/Pause'
import { PlayIcon } from '@phosphor-icons/react/dist/csr/Play'
import { SpeakerHighIcon } from '@phosphor-icons/react/dist/csr/SpeakerHigh'
import { SpeakerSlashIcon } from '@phosphor-icons/react/dist/csr/SpeakerSlash'
import { SkipBackIcon } from '@phosphor-icons/react/dist/csr/SkipBack'
import { SkipForwardIcon } from '@phosphor-icons/react/dist/csr/SkipForward'
import { WaveformIcon } from '@phosphor-icons/react/dist/csr/Waveform'
import { UploadSimpleIcon } from '@phosphor-icons/react/dist/csr/UploadSimple'
import { formatTime } from '../meetings/model'
import { useObjectUrl } from './useObjectUrl'

export interface PlayerHandle {
  seek: (seconds: number) => void
}
interface Props {
  file?: File
  duration: number
  speaker?: string
  onPosition: (seconds: number) => void
  onFile: (file: File) => void
}

export const AudioPlayer = forwardRef<PlayerHandle, Props>(function AudioPlayer(
  { file, duration: fallbackDuration, speaker, onPosition, onFile },
  ref,
) {
  const url = useObjectUrl(file)
  const audio = useRef<HTMLAudioElement>(null)
  const picker = useRef<HTMLInputElement>(null)
  const positionRef = useRef(file ? 0 : 255)
  const [position, setPosition] = useState(file ? 0 : 255)
  const [duration, setDuration] = useState(file ? 0 : fallbackDuration)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [volume, setVolume] = useState(0.8)
  const [muted, setMuted] = useState(false)
  const [error, setError] = useState('')
  const commitPosition = (seconds: number) => {
    positionRef.current = seconds
    setPosition(seconds)
    onPosition(seconds)
  }
  const seek = (seconds: number) => {
    const value = Math.max(0, Math.min(duration, seconds))
    if (audio.current && file) audio.current.currentTime = value
    commitPosition(value)
  }
  useImperativeHandle(ref, () => ({ seek }))

  useEffect(() => {
    if (!playing || file) return
    let last = performance.now()
    const timer = window.setInterval(() => {
      const now = performance.now()
      const value = Math.min(
        fallbackDuration,
        positionRef.current + ((now - last) / 1000) * speed,
      )
      last = now
      positionRef.current = value
      setPosition(value)
      onPosition(value)
      if (value >= fallbackDuration) setPlaying(false)
    }, 100)
    return () => window.clearInterval(timer)
  }, [playing, file, speed, fallbackDuration, onPosition])
  useEffect(() => {
    const element = audio.current
    return () => element?.pause()
  }, [])

  async function toggle() {
    if (playing) {
      audio.current?.pause()
      setPlaying(false)
      return
    }
    if (position >= duration) seek(0)
    if (file) {
      try {
        await audio.current?.play()
      } catch {
        setError('Không thể phát file này. Hãy thử định dạng MP3 hoặc WAV.')
        return
      }
    }
    setPlaying(true)
  }
  const ratio = duration ? position / duration : 0
  return (
    <section className="audio-region" aria-label="Player audio cuộc họp">
      <div className="audio-player">
        <div className="audio-caption">
          <span>
            <WaveformIcon size={17} />
            Bản ghi cuộc họp
          </span>
          <small>{file?.name || 'Sprint_42_Audio.mp3 · mô phỏng'}</small>
          <button
            className="button secondary small"
            aria-label="Chọn audio để nghe thử"
            title={file?.name || 'Chọn audio để nghe thử'}
            onClick={() => picker.current?.click()}
          >
            <UploadSimpleIcon />
            <span>Chọn audio</span>
          </button>
          <input
            hidden
            type="file"
            accept="audio/*,.webm,.mp4"
            ref={picker}
            aria-label="Chọn audio cho player"
            onChange={(e) => {
              const chosen = e.target.files?.[0]
              if (chosen) onFile(chosen)
              e.target.value = ''
            }}
          />
        </div>
        <div
          className="waveform"
          style={{ '--progress': `${ratio * 100}%` } as React.CSSProperties}
        >
          <div className="waveform-bars" aria-hidden="true">
            {Array.from({ length: 180 }, (_, i) => (
              <i
                key={i}
                className={i / 180 <= ratio ? 'heard' : ''}
                style={{
                  height: `${10 + Math.abs(Math.sin(i * 1.73) * Math.cos(i * 0.39)) * 36}px`,
                }}
              />
            ))}
          </div>
          <input
            aria-label="Tua bản ghi"
            type="range"
            min="0"
            max={duration || 1}
            value={Math.min(position, duration || 0)}
            step=".1"
            disabled={!duration}
            onChange={(e) => seek(Number(e.target.value))}
          />
        </div>
        <div className="time-ruler" aria-hidden="true">
          {[0, 0.2, 0.4, 0.6, 0.8, 1].map((n) => (
            <span key={n}>{formatTime(n * duration)}</span>
          ))}
        </div>
        <div className="audio-controls">
          <div className="transport">
            <button
              className="icon-button skip-button"
              title="Lùi 10 giây"
              aria-label="Lùi 10 giây"
              onClick={() => seek(position - 10)}
              disabled={!duration}
            >
              <SkipBackIcon />
              <span>10</span>
            </button>
            <button
              className="play-button"
              aria-label={
                playing
                  ? 'Tạm dừng'
                  : file
                    ? 'Phát audio'
                    : 'Phát thử giao diện'
              }
              onClick={() => void toggle()}
              disabled={!duration}
            >
              {playing ? (
                <PauseIcon weight="fill" />
              ) : (
                <PlayIcon weight="fill" />
              )}
            </button>
            <button
              className="icon-button skip-button"
              title="Tiến 10 giây"
              aria-label="Tiến 10 giây"
              onClick={() => seek(position + 10)}
              disabled={!duration}
            >
              <SkipForwardIcon />
              <span>10</span>
            </button>
          </div>
          <div className="play-time mono">
            <strong>{formatTime(position)}</strong>
            <span>/ {formatTime(duration)}</span>
          </div>
          <span className="current-speaker">
            <span className="playing-dot" />
            <span>{file ? 'Audio trên máy' : speaker || 'Nguyên Tài'}</span>
          </span>
          <div className="playback-options">
            <select
              aria-label="Tốc độ phát"
              value={speed}
              onChange={(e) => {
                const value = Number(e.target.value)
                setSpeed(value)
                if (audio.current) audio.current.playbackRate = value
              }}
            >
              {[0.75, 1, 1.25, 1.5, 2].map((n) => (
                <option key={n} value={n}>
                  {n}×
                </option>
              ))}
            </select>
            <button
              className="icon-button volume-button"
              aria-label={muted ? 'Bật âm thanh' : 'Tắt âm thanh'}
              onClick={() => setMuted((v) => !v)}
            >
              {muted ? <SpeakerSlashIcon /> : <SpeakerHighIcon />}
            </button>
            <input
              className="volume-slider"
              aria-label="Âm lượng"
              type="range"
              min="0"
              max="1"
              step=".01"
              value={volume}
              onChange={(e) => {
                const value = Number(e.target.value)
                setVolume(value)
                if (audio.current) audio.current.volume = value
              }}
            />
          </div>
        </div>
      </div>
      <p className="audio-note">
        {file
          ? 'File phát tại máy bạn; waveform và transcript bên dưới vẫn là minh họa.'
          : 'Player đang mô phỏng. Chọn audio trên máy để nghe bản ghi thật.'}
      </p>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <audio
        ref={audio}
        src={url}
        preload="metadata"
        muted={muted}
        onLoadedMetadata={(e) => {
          const measured = e.currentTarget.duration
          // MediaRecorder WebM may omit a duration header; recording flow measures wall time.
          const value = Number.isFinite(measured) ? measured : fallbackDuration
          if (!Number.isFinite(value) || value <= 0) {
            setError(
              'Không đọc được thời lượng audio. Hãy thử file MP3 hoặc WAV.',
            )
            return
          }
          setDuration(value)
          commitPosition(0)
          e.currentTarget.volume = volume
          e.currentTarget.playbackRate = speed
          setError('')
        }}
        onTimeUpdate={(e) => {
          if (file) commitPosition(e.currentTarget.currentTime)
        }}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
        onError={() => {
          if (file) {
            setError('Trình duyệt không đọc được file audio này.')
            setPlaying(false)
          }
        }}
      />
    </section>
  )
})
