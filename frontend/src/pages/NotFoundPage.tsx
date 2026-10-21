import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <main className="not-found">
      <p className="eyebrow">404</p>
      <h1>Không tìm thấy trang</h1>
      <p>Đường dẫn bạn vừa mở không tồn tại trong ứng dụng.</p>
      <Link className="button primary" to="/meetings">
        Về danh sách cuộc họp
      </Link>
    </main>
  )
}
