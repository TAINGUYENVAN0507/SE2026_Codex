import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useLocation } from 'react-router-dom'
import { onSessionExpired } from '../../api/sessionEvents'
import { useEndSession } from './useEndSession'

export function SessionEvents() {
  const endSession = useEndSession()
  const client = useQueryClient()
  const location = useLocation()
  useEffect(() => {
    // Observer có thể tạo lại query trước khi route bảo vệ được unmount.
    // Dọn lần cuối sau khi màn đăng nhập đã commit, không giữ dữ liệu phiên cũ.
    if (location.pathname === '/login') client.clear()
  }, [client, location.pathname, location.key])
  useEffect(
    () =>
      onSessionExpired(() => {
        if (location.pathname !== '/login') void endSession(true)
      }),
    [endSession, location.pathname],
  )
  return null
}
