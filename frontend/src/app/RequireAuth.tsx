import { Navigate, Outlet, useLocation } from 'react-router-dom'

export const DEMO_AUTH_KEY = 'meeting-demo-authenticated'

export function RequireAuth() {
  const location = useLocation()
  if (sessionStorage.getItem(DEMO_AUTH_KEY) === 'true') return <Outlet />

  const next = `${location.pathname}${location.search}${location.hash}`
  return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />
}
