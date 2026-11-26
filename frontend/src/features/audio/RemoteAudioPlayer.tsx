import {
  forwardRef,
  useEffect,
  useRef,
  useState,
  type ComponentProps,
} from 'react'
import { AudioPlayer, type PlayerHandle } from './AudioPlayer'
import type { MeetingDetail } from '../../api/client'
import { parseApiError } from '../../api/errors'

type Props = Omit<
  ComponentProps<typeof AudioPlayer>,
  'src' | 'onPlaybackError' | 'ref'
> & {
  meetingId: string
  audioInfo: MeetingDetail['audio']
  preview?: boolean
}
export const RemoteAudioPlayer = forwardRef<PlayerHandle, Props>(
  function RemoteAudioPlayer(
    { meetingId, audioInfo, preview = false, ...props },
    ref,
  ) {
    const [unavailable, setUnavailable] = useState<
      'expired' | 'missing' | null
    >(null)
    // Chụp mốc lúc mở player; trong phiên phát, probe 410 xác nhận hết hạn từ server.
    const [openedAt] = useState(() => Date.now())
    const probe = useRef<AbortController | null>(null)
    useEffect(() => () => probe.current?.abort(), [])
    const src = `/api/v1/meetings/${encodeURIComponent(meetingId)}/audio`
    async function checkAvailability() {
      probe.current?.abort()
      const controller = new AbortController()
      probe.current = controller
      try {
        const response = await fetch(src, {
          headers: { Range: 'bytes=0-0' },
          credentials: 'include',
          signal: controller.signal,
        })
        if (response.status === 404) {
          const error = await parseApiError(response)
          // API hiện trả NOT_FOUND cho file mất; nhận cả mã chuyên biệt khi có.
          if (
            !controller.signal.aborted &&
            ['AUDIO_NOT_FOUND', 'NOT_FOUND'].includes(error.code)
          )
            setUnavailable('missing')
        } else {
          if (response.status === 410 && !controller.signal.aborted)
            setUnavailable('expired')
          await response.body?.cancel()
        }
      } catch {
        /* Giữ lỗi phát chung nếu probe không xác nhận được mất file/hết hạn. */
      }
    }
    const retention = audioInfo.retention_until
      ? new Date(audioInfo.retention_until)
      : null
    const reason =
      unavailable ??
      (!audioInfo.available
        ? retention &&
          Number.isFinite(retention.getTime()) &&
          retention.getTime() <= openedAt
          ? 'expired'
          : 'missing'
        : null)
    const metadata =
      retention && Number.isFinite(retention.getTime()) ? (
        <p className="audio-retention">
          Lưu audio đến{' '}
          <time dateTime={audioInfo.retention_until!}>
            {new Intl.DateTimeFormat('vi-VN', {
              dateStyle: 'short',
              timeStyle: 'short',
            }).format(retention)}
          </time>{' '}
          (giờ địa phương)
        </p>
      ) : null
    return (
      <>
        {reason ? (
          <section className="audio-expired" aria-label="Player audio cuộc họp">
            <p role="status">
              {reason === 'expired'
                ? 'Audio đã hết hạn lưu trữ'
                : 'Không tìm thấy file audio'}
            </p>
            <p>Transcript và nội dung cuộc họp vẫn có thể đọc được.</p>
            {metadata}
          </section>
        ) : (
          <AudioPlayer
            {...props}
            src={preview ? undefined : src}
            metadata={metadata}
            onPlaybackError={() => void checkAvailability()}
            ref={ref}
          />
        )}
      </>
    )
  },
)
