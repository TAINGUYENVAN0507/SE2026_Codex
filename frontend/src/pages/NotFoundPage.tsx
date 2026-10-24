import { Link } from 'react-router-dom'

export function NotFoundPage({ meeting = false }: { meeting?: boolean }) {
  return (
    <main className="not-found">
      <p className="eyebrow">404</p>
      <h1>{meeting ? 'Không tìm thấy cuộc họp' : 'Không tìm thấy trang'}</h1>
      <p>
        {meeting
          ? 'Cuộc họp không tồn tại hoặc bạn không có quyền truy cập.'
          : 'Đường dẫn bạn vừa mở không tồn tại trong ứng dụng.'}
      </p>
      <Link className="button primary" to="/meetings">
        Về danh sách cuộc họp
      </Link>
    </main>
  )
}
