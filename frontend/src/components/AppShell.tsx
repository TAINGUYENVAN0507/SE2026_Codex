import { Outlet } from 'react-router-dom'

export function AppShell() {
  return (
    <>
      <div className="demo-strip">
        <span className="demo-indicator" />
        Bản xem thử{' '}
        <span className="demo-description">
          {import.meta.env.DEV && import.meta.env.VITE_API_MOCK !== '0'
            ? 'API mô phỏng bằng dữ liệu mẫu · không lưu lên máy chủ'
            : 'Giao diện thử nghiệm · kiểm tra dữ liệu trước khi sử dụng'}
        </span>
      </div>
      <Outlet />
    </>
  )
}
