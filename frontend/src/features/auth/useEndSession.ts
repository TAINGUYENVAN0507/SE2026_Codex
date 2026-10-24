import { useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router-dom'
import { useMeetings } from '../meetings/DemoStore'

export function useEndSession() {
  const client = useQueryClient()
  const navigate = useNavigate()
  const location = useLocation()
  const { reset } = useMeetings()
  return async (returnToPage = false) => {
    await client.cancelQueries()
    client.clear()
    reset()
    const next = `${location.pathname}${location.search}${location.hash}`
    navigate(
      returnToPage ? `/login?next=${encodeURIComponent(next)}` : '/login',
      { replace: true },
    )
  }
}
