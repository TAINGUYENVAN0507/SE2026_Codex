import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { TrashIcon } from '@phosphor-icons/react/dist/csr/Trash'
import { deleteMeeting } from '../../api/client'
import { ApiError, isServiceBusy } from '../../api/errors'
import { Dialog } from '../../components/Dialog'
import { useMeetings } from './DemoStore'

export function DeleteMeetingButton({
  meetingId,
  jobId,
}: {
  meetingId: string
  jobId?: string
}) {
  const client = useQueryClient()
  const navigate = useNavigate()
  const { remove } = useMeetings()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [retryDelete, setRetryDelete] = useState(false)
  async function confirm() {
    if (busy) return
    setRetryDelete(false)
    setBusy(true)
    setError('')
    try {
      await deleteMeeting(meetingId)
      const kinds = new Set([
        'meeting',
        'transcript',
        'summary',
        'action-items',
        'edits',
      ])
      const predicate = ({ queryKey }: { queryKey: readonly unknown[] }) =>
        queryKey[0] === 'meetings' ||
        (kinds.has(String(queryKey[0])) && queryKey[1] === meetingId) ||
        (queryKey[0] === 'job' && queryKey[1] === jobId)
      await client.cancelQueries({ predicate })
      client.removeQueries({ predicate })
      remove(meetingId)
      navigate('/meetings', { replace: true })
    } catch (cause) {
      setRetryDelete(isServiceBusy(cause))
      setError(
        `Không xóa được cuộc họp. ${cause instanceof ApiError ? cause.message : 'Hãy thử lại.'}`,
      )
      setBusy(false)
    }
  }
  return (
    <>
      <button
        className="button secondary small delete-meeting"
        aria-label="Xóa cuộc họp"
        title="Xóa cuộc họp"
        onClick={() => {
          setRetryDelete(false)
          setError('')
          setOpen(true)
        }}
      >
        <TrashIcon aria-hidden="true" /> <span>Xóa cuộc họp</span>
      </button>
      {open && (
        <Dialog
          title="Xóa cuộc họp?"
          onClose={() => {
            if (!busy) setOpen(false)
          }}
        >
          <p>
            Thao tác này sẽ xóa audio, transcript, tóm tắt, công việc (action
            item) và lịch sử chỉnh sửa. Bạn không thể khôi phục sau khi xóa.
          </p>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <div className="delete-actions">
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => setOpen(false)}
            >
              Giữ lại
            </button>
            <button
              className="button danger"
              disabled={busy}
              onClick={() => void confirm()}
            >
              {busy
                ? 'Đang xóa…'
                : retryDelete
                  ? 'Thử xóa lại'
                  : 'Xóa vĩnh viễn'}
            </button>
          </div>
        </Dialog>
      )}
    </>
  )
}
