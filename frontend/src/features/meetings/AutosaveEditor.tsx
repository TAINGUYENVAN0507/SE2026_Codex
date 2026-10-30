import { useEffect, useState } from 'react'
import { patchSegment } from '../../api/client'
import { createAutosave, type SaveResult, type SaveSnapshot } from './autosave'

const DEBOUNCE_MS = 500 // VT-019: giá trị thiết kế, không phải SLA của đề.
const labels = {
  saved: 'Đã lưu',
  dirty: 'Chưa lưu',
  saving: 'Đang lưu…',
  error: 'Chưa lưu',
  conflict: 'Xung đột - bản nháp được giữ',
}

export function AutosaveEditor({
  meetingId,
  segmentId,
  text,
  version,
  onSaved,
  onClose,
  onConflict,
}: {
  meetingId: string
  segmentId: string
  text: string
  version: number
  onSaved: (value: SaveResult) => void
  onClose: () => void
  onConflict: () => void
}) {
  const [state, setState] = useState<SaveSnapshot>({
    text,
    version,
    status: 'saved',
    error: '',
  })
  const [session] = useState(() =>
    createAutosave(
      { text, version },
      (patch) => patchSegment(meetingId, segmentId, patch),
      setState,
      onSaved,
      onConflict,
    ),
  )
  useEffect(() => {
    session.resume()
    return () => session.close()
  }, [session])
  useEffect(() => {
    if (state.status !== 'dirty') return
    const timer = window.setTimeout(() => {
      void session.flush()
    }, DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
  }, [session, state.text, state.status])
  const finish = async () => {
    if (await session.flush()) onClose()
  }
  return (
    <div className="segment-editor">
      <textarea
        autoFocus
        aria-label="Chỉnh sửa transcript"
        value={state.text}
        onChange={(event) => session.edit(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') onClose()
          if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
            event.preventDefault()
            void finish()
          }
        }}
      />
      {state.error && (
        <p role="alert" className="form-error">
          {state.error}
        </p>
      )}
      <div className="editor-footer">
        <span role="status" aria-live="polite">
          {labels[state.status]}
        </span>
        <div>
          {state.status === 'error' && (
            <button
              className="button quiet small"
              onClick={() => void session.flush()}
            >
              Thử lại
            </button>
          )}
          <button className="button quiet small" onClick={onClose}>
            Hủy
          </button>
          <button
            className="button primary small"
            onClick={() => void finish()}
          >
            Lưu thay đổi
          </button>
        </div>
      </div>
      <small>
        Tự lưu sau khi ngừng gõ. Hủy chỉ đóng editor; phần đã lưu vẫn được giữ.
      </small>
    </div>
  )
}
