import { Component, type PropsWithChildren } from 'react'
import { Link } from 'react-router-dom'

export class RouteErrorBoundary extends Component<
  PropsWithChildren,
  { failed: boolean }
> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  render() {
    if (this.state.failed)
      return (
        <main className="not-found" role="alert">
          <h1>Trang gặp sự cố</h1>
          <p>
            Không thể hiển thị nội dung lúc này. Bạn có thể tải lại để thử lại.
          </p>
          <button
            className="button primary"
            onClick={() => window.location.reload()}
          >
            Tải lại
          </button>
          <Link className="button quiet" to="/meetings">
            Về danh sách cuộc họp
          </Link>
        </main>
      )
    return this.props.children
  }
}
