import { useEffect, useState } from 'react'
import { onNetworkFailure } from '../api/networkEvents'

export function ConnectivityNotice() {
  const [online, setOnline] = useState(() => navigator.onLine)
  const [networkError, setNetworkError] = useState(false)
  useEffect(() => {
    const connected = () => setOnline(true)
    const disconnected = () => setOnline(false)
    window.addEventListener('online', connected)
    window.addEventListener('offline', disconnected)
    const unsubscribe = onNetworkFailure(() => setNetworkError(true))
    return () => {
      window.removeEventListener('online', connected)
      window.removeEventListener('offline', disconnected)
      unsubscribe()
    }
  }, [])
  useEffect(() => {
    if (!networkError) return
    const timer = window.setTimeout(() => setNetworkError(false), 6000)
    return () => window.clearTimeout(timer)
  }, [networkError])
  return (
    <>
      {!online && (
        <div className="offline-banner" role="status">
          Bạn đang mất kết nối mạng. Các thay đổi chưa gửi sẽ chưa được lưu.
        </div>
      )}
      {networkError && (
        <div className="network-toast" role="status">
          <span>Không thể kết nối máy chủ. Hãy kiểm tra mạng rồi thử lại.</span>
          <button
            className="button quiet small"
            aria-label="Đóng thông báo kết nối"
            onClick={() => setNetworkError(false)}
          >
            Đóng
          </button>
        </div>
      )}
    </>
  )
}
