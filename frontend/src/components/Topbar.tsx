import { NavLink } from 'react-router-dom'
import { Brand } from './Brand'
import { useState } from 'react'
import { useMe } from '../features/auth/useMe'
import { useEndSession } from '../features/auth/useEndSession'
import { logout } from '../api/client'

export function Topbar() {
  const me = useMe()
  const endSession = useEndSession()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function signOut() {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      await logout()
      await endSession()
    } catch {
      setError('Chưa thể đăng xuất. Hãy kiểm tra kết nối và thử lại.')
      setBusy(false)
    }
  }
  const name = me.data?.user.display_name || 'Tài khoản'
  return (
    <header className="topbar">
      <div className="top-left">
        <Brand />
        <nav aria-label="Điều hướng chính">
          <NavLink to="/meetings" className="nav-item">
            Cuộc họp
          </NavLink>
        </nav>
      </div>
      <div className="top-right">
        <span className="avatar dark">
          {name
            .split(/\s+/)
            .filter(Boolean)
            .slice(-2)
            .map((part) => part[0])
            .join('')}
        </span>
        <span className="profile-name">{name}</span>
        <button
          className="button quiet small"
          onClick={() => void signOut()}
          disabled={busy}
        >
          {busy ? 'Đang đăng xuất…' : 'Đăng xuất'}
        </button>
        {error && (
          <span className="form-error" role="alert">
            {error}
          </span>
        )}
      </div>
    </header>
  )
}
