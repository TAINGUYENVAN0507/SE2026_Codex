import { Outlet } from 'react-router-dom'

export function AppShell() {
  return (
    <>
      <div className="demo-strip">
        <span className="demo-indicator" />
        Bản xem thử{' '}
        <span className="demo-description">
          Dữ liệu mẫu · thay đổi chỉ giữ trong phiên này
        </span>
      </div>
      <Outlet />
    </>
  )
}
