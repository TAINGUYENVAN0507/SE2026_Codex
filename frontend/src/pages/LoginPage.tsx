import { EyeIcon } from '@phosphor-icons/react/dist/csr/Eye'
import { EyeSlashIcon } from '@phosphor-icons/react/dist/csr/EyeSlash'
import { ArrowRightIcon } from '@phosphor-icons/react/dist/csr/ArrowRight'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Brand } from '../components/Brand'
import { DEMO_AUTH_KEY } from '../app/RequireAuth'
import { safeNext } from '../app/safeNext'

export function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [visible, setVisible] = useState(false)
  return (
    <main className="login-page">
      <section className="login-story">
        <Brand />
        <div className="story-copy">
          <h1>
            Từ cuộc họp
            <br />
            đến việc cần làm.
          </h1>
          <p>Nghe lại, chỉnh sửa và lưu những điều quan trọng.</p>
          <div className="story-wave" aria-hidden="true">
            {Array.from({ length: 63 }, (_, i) => (
              <i
                key={i}
                className={i > 22 && i < 33 ? 'heard' : ''}
                style={{
                  height: `${16 + Math.abs(Math.sin(i * 1.71) * Math.cos(i * 0.23)) * 94}px`,
                }}
              />
            ))}
          </div>
        </div>
        <span className="story-caption">
          Vietnamese Meeting Minutes Assistant
        </span>
      </section>
      <section className="login-form-zone">
        <form
          className="login-form"
          onSubmit={(e) => {
            e.preventDefault()
            e.currentTarget.reset()
            sessionStorage.setItem(DEMO_AUTH_KEY, 'true')
            navigate(safeNext(searchParams.get('next')), { replace: true })
          }}
        >
          <h2>Chào mừng trở lại</h2>
          <p>Đăng nhập vào không gian cuộc họp của bạn.</p>
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              name="email"
              placeholder="ban@example.com"
              autoComplete="email"
              required
            />
          </label>
          <label className="field">
            <span>Mật khẩu</span>
            <span className="password-field">
              <input
                type={visible ? 'text' : 'password'}
                name="password"
                placeholder="Nhập mật khẩu"
                autoComplete="current-password"
                required
              />
              <button
                className="icon-button"
                type="button"
                onClick={() => setVisible((v) => !v)}
                aria-label={visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
              >
                {visible ? <EyeSlashIcon /> : <EyeIcon />}
              </button>
            </span>
          </label>
          <button className="button primary login-submit" type="submit">
            Đăng nhập <ArrowRightIcon />
          </button>
          <p className="login-help">Tài khoản do quản trị viên cung cấp.</p>
          <Link
            className="text-link preview-link"
            to="/meetings"
            onClick={() => sessionStorage.setItem(DEMO_AUTH_KEY, 'true')}
          >
            Xem thử giao diện <ArrowRightIcon />
          </Link>
        </form>
      </section>
    </main>
  )
}
