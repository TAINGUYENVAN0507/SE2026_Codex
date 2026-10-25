import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useMe } from '../features/auth/useMe'

export function RequireAuth() {
  const location = useLocation()
  const me = useMe()
  if (me.isPending)
    return (
      <main
        className="missing-meeting"
        role="status"
        aria-label="Đang kiểm tra phiên đăng nhập"
      >
        <div className="transcript-skeleton" aria-hidden="true" />
        Đang kiểm tra phiên đăng nhập…
      </main>
    )
  if (me.isError)
    return (
      <main className="missing-meeting" role="alert">
        <p>Không thể kiểm tra phiên đăng nhập. Hãy thử lại.</p>
        <button className="button primary" onClick={() => void me.refetch()}>
          Thử lại
        </button>
      </main>
    )
  if (me.data) return <Outlet />

  const next = `${location.pathname}${location.search}${location.hash}`
  return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />
}
