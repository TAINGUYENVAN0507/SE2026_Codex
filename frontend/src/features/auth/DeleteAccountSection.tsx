import { useRef, useState } from 'react'
import { deleteAccount } from '../../api/client'
import { ApiError } from '../../api/errors'
import { Dialog } from '../../components/Dialog'
import { useEndSession } from './useEndSession'

export function DeleteAccountSection({
  email,
  available,
}: {
  email: string
  available: boolean
}) {
  const [open, setOpen] = useState(false)
  const [confirmation, setConfirmation] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const inFlight = useRef(false)
  const endSession = useEndSession()
  const matches =
    confirmation.trim().toLowerCase() === email.trim().toLowerCase() &&
    Boolean(email)
  async function submit() {
    if (!available || !matches || inFlight.current) return
    inFlight.current = true
    setBusy(true)
    setError('')
    try {
      await deleteAccount()
      await endSession()
    } catch (cause) {
      setError(
        cause instanceof ApiError && [404, 405, 501].includes(cause.status)
          ? 'Chức năng xóa tài khoản hiện chưa khả dụng. Tài khoản của bạn vẫn được giữ nguyên.'
          : cause instanceof ApiError && cause.status === 401
            ? 'Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại.'
            : 'Chưa thể xóa tài khoản. Hãy kiểm tra kết nối và thử lại.',
      )
      inFlight.current = false
      setBusy(false)
    }
  }
  return (
    <section
      className="settings-section account-erasure"
      aria-labelledby="delete-account-heading"
    >
      <div>
        <h2 id="delete-account-heading">Xóa tài khoản</h2>
        <p>
          Xóa vĩnh viễn tài khoản và toàn bộ cuộc họp, audio, transcript, tóm
          tắt, công việc cùng lịch sử chỉnh sửa. Bạn sẽ không thể khôi phục dữ
          liệu sau khi xóa.
        </p>
      </div>
      {!available && (
        <p
          className="settings-unavailable"
          id="deletion-unavailable"
          role="status"
        >
          Chức năng xóa tài khoản hiện chưa khả dụng.
        </p>
      )}
      <button
        className="button danger"
        disabled={!available}
        aria-describedby={!available ? 'deletion-unavailable' : undefined}
        onClick={() => {
          setConfirmation('')
          setError('')
          setOpen(true)
        }}
      >
        Xóa tài khoản
      </button>
      {open && (
        <Dialog
          title="Xóa tài khoản vĩnh viễn?"
          onClose={() => {
            if (!inFlight.current) setOpen(false)
          }}
        >
          <p>
            Mọi cuộc họp và dữ liệu liên quan của bạn sẽ bị xóa vĩnh viễn. Thao
            tác này không thể hoàn tác.
          </p>
          <form
            className="delete-account-form"
            onSubmit={(e) => {
              e.preventDefault()
              void submit()
            }}
          >
            <label htmlFor="confirm-account-email">
              Gõ lại email <strong>{email}</strong> để xác nhận
            </label>
            <input
              id="confirm-account-email"
              type="email"
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
              value={confirmation}
              disabled={busy}
              onChange={(e) => setConfirmation(e.target.value)}
              aria-describedby="delete-account-warning"
            />
            <p id="delete-account-warning">
              Chỉ bấm xóa khi bạn đã lưu những nội dung cần giữ lại.
            </p>
            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}
            <div className="delete-actions">
              <button
                type="button"
                className="button secondary"
                disabled={busy}
                onClick={() => setOpen(false)}
              >
                Giữ tài khoản
              </button>
              <button
                type="submit"
                className="button danger"
                disabled={!matches || busy}
              >
                {busy ? 'Đang xóa…' : 'Xóa tài khoản vĩnh viễn'}
              </button>
            </div>
          </form>
        </Dialog>
      )}
    </section>
  )
}
