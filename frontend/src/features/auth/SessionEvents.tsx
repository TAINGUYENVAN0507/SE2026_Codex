import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { onSessionExpired } from '../../api/sessionEvents'
import { useEndSession } from './useEndSession'

export function SessionEvents() {
  const endSession = useEndSession()
  const location = useLocation()
  useEffect(
    () =>
      onSessionExpired(() => {
        if (location.pathname !== '/login') void endSession(true)
      }),
    [endSession, location.pathname],
  )
  return null
}
