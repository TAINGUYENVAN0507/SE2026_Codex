import { useCallback, useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router-dom'
import { useMeetings } from '../meetings/DemoStore'

export function useEndSession() {
  const client = useQueryClient()
  const navigate = useNavigate()
  const location = useLocation()
  const { reset } = useMeetings()
  const ending = useRef(false)
  useEffect(() => {
    ending.current = false
  }, [location.key])

  return useCallback(
    async (returnToPage = false) => {
      // Các request có thể cùng trả 401 trước khi router kịp chuyển trang.
      if (ending.current) return
      ending.current = true
      await client.cancelQueries()
      client.clear()
      reset()
      const next = `${location.pathname}${location.search}${location.hash}`
      navigate(
        returnToPage ? `/login?next=${encodeURIComponent(next)}` : '/login',
        {
          replace: true,
          state: returnToPage ? { sessionExpired: true } : null,
        },
      )
    },
    [
      client,
      navigate,
      location.pathname,
      location.search,
      location.hash,
      reset,
    ],
  )
}
