import { NavLink } from 'react-router-dom'
import { Brand } from './Brand'

export function Topbar() {
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
        <span className="avatar dark">VT</span>
        <span className="profile-name">Văn Tường</span>
        <NavLink to="/login" className="login-link">
          Đăng nhập
        </NavLink>
      </div>
    </header>
  )
}
