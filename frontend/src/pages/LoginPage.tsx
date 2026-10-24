import { EyeIcon } from '@phosphor-icons/react/dist/csr/Eye'
import { EyeSlashIcon } from '@phosphor-icons/react/dist/csr/EyeSlash'
import { ArrowRightIcon } from '@phosphor-icons/react/dist/csr/ArrowRight'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { Brand } from '../components/Brand'
import { safeNext } from '../app/safeNext'
import { login } from '../api/client'
import { ApiError } from '../api/errors'
import { ME_QUERY_KEY } from '../features/auth/useMe'

export function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [visible, setVisible] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const queryClient = useQueryClient()

  async function submit() {
    if (submitting) return
    setSubmitting(true)
    setError('')
    try {
      const session = await login(email.trim(), password)
      queryClient.clear()
      queryClient.setQueryData(ME_QUERY_KEY, session)
      setPassword('')
      navigate(safeNext(searchParams.get('next')), { replace: true })
    } catch (cause) {
      setPassword('')
      setError(
        cause instanceof ApiError && cause.code === 'INVALID_CREDENTIALS'
          ? 'Email hoặc mật khẩu không chính xác.'
          : cause instanceof ApiError && cause.code === 'NETWORK_ERROR'
            ? 'Không thể kết nối máy chủ. Hãy kiểm tra mạng rồi thử lại.'
            : 'Không thể đăng nhập. Hãy thử lại.',
      )
    } finally {
      setSubmitting(false)
    }
  }
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
            void submit()
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
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={submitting}
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
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={submitting}
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
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button
            className="button primary login-submit"
            type="submit"
            disabled={submitting}
          >
            {submitting ? 'Đang đăng nhập…' : 'Đăng nhập'} <ArrowRightIcon />
          </button>
          <p className="login-help">Tài khoản do quản trị viên cung cấp.</p>
        </form>
      </section>
    </main>
  )
}
