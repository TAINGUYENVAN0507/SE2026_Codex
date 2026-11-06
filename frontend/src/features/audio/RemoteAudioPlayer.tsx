import {
  forwardRef,
  useEffect,
  useRef,
  useState,
  type ComponentProps,
} from 'react'
import { AudioPlayer, type PlayerHandle } from './AudioPlayer'
import type { MeetingDetail } from '../../api/client'

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
    const [expired, setExpired] = useState(false)
    const probe = useRef<AbortController | null>(null)
    useEffect(() => () => probe.current?.abort(), [])
    const src = `/api/v1/meetings/${encodeURIComponent(meetingId)}/audio`
    async function checkExpiration() {
      probe.current?.abort()
      const controller = new AbortController()
      probe.current = controller
      try {
        const response = await fetch(src, {
          headers: { Range: 'bytes=0-0' },
          credentials: 'include',
          signal: controller.signal,
        })
        if (response.status === 410 && !controller.signal.aborted)
          setExpired(true)
        await response.body?.cancel()
      } catch {
        /* AudioPlayer đã hiện lỗi phát; chỉ thay bằng hết hạn khi server xác nhận 410. */
      }
    }
    const retention = audioInfo.retention_until
      ? new Date(audioInfo.retention_until)
      : null
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
        {!audioInfo.available || expired ? (
          <section className="audio-expired" aria-label="Player audio cuộc họp">
            <p role="status">Audio đã hết hạn lưu trữ</p>
            <p>Transcript và nội dung cuộc họp vẫn có thể đọc được.</p>
            {metadata}
          </section>
        ) : (
          <AudioPlayer
            {...props}
            src={preview ? undefined : src}
            metadata={metadata}
            onPlaybackError={() => void checkExpiration()}
            ref={ref}
          />
        )}
      </>
    )
  },
)
