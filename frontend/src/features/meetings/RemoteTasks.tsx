import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createActionItem,
  deleteActionItem,
  listActionItems,
  patchActionItem,
  type ActionItemData,
} from '../../api/client'
import { ApiError } from '../../api/errors'
import { formatDate, type Meeting } from './model'

interface Draft {
  description: string
  assigneeName: string
  speakerId: string
  dueDate: string
}

function draftFrom(item?: ActionItemData): Draft {
  return {
    description: item?.description ?? '',
    assigneeName: item?.assignee_name ?? '',
    speakerId: item?.assignee_speaker_id ?? '',
    dueDate: item?.due_date ?? '',
  }
}

export function RemoteTasks({ meeting }: { meeting: Meeting }) {
  const queryClient = useQueryClient()
  const queryKey = ['action-items', meeting.id]
  const query = useQuery({
    queryKey,
    queryFn: () => listActionItems(meeting.id),
  })
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState<Draft>(() => draftFrom())
  const [error, setError] = useState('')
  const [conflict, setConflict] = useState(false)
  const [busy, setBusy] = useState(false)

  function validate(): boolean {
    const length = draft.description.trim().length
    if (length < 1 || length > 1000) {
      setError('Mô tả công việc cần có từ 1 đến 1000 ký tự.')
      return false
    }
    return true
  }

  function showError(cause: unknown) {
    if (cause instanceof ApiError && cause.code === 'VERSION_CONFLICT')
      setConflict(true)
    else
      setError(
        cause instanceof ApiError
          ? cause.message
          : 'Không thể lưu công việc. Hãy thử lại.',
      )
  }

  async function create() {
    if (!validate() || busy) return
    setBusy(true)
    setError('')
    try {
      await createActionItem(meeting.id, {
        description: draft.description.trim(),
        assignee_name: draft.assigneeName.trim() || null,
        assignee_speaker_id: draft.speakerId || null,
        due_date: draft.dueDate || null,
        status: 'open',
      })
      await queryClient.invalidateQueries({ queryKey })
      setDraft(draftFrom())
    } catch (cause) {
      showError(cause)
    } finally {
      setBusy(false)
    }
  }

  async function update(item: ActionItemData) {
    if (!validate() || busy) return
    setBusy(true)
    setError('')
    try {
      await patchActionItem(meeting.id, item.id, {
        description: draft.description.trim(),
        assignee_name: draft.assigneeName.trim() || null,
        assignee_speaker_id: draft.speakerId || null,
        due_date: draft.dueDate || null,
        version: item.version,
      })
      await queryClient.invalidateQueries({ queryKey })
      setEditing(null)
    } catch (cause) {
      showError(cause)
    } finally {
      setBusy(false)
    }
  }

  async function toggle(item: ActionItemData) {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      await patchActionItem(meeting.id, item.id, {
        status: item.status === 'done' ? 'open' : 'done',
        version: item.version,
      })
      await queryClient.invalidateQueries({ queryKey })
    } catch (cause) {
      showError(cause)
    } finally {
      setBusy(false)
    }
  }

  async function remove(item: ActionItemData) {
    if (!window.confirm('Xóa công việc này?') || busy) return
    setBusy(true)
    setError('')
    try {
      await deleteActionItem(meeting.id, item.id, item.version)
      await queryClient.invalidateQueries({ queryKey })
    } catch (cause) {
      showError(cause)
    } finally {
      setBusy(false)
    }
  }

  function fields(prefix: string) {
    return (
      <>
        <input
          aria-label={`${prefix} nội dung`}
          placeholder="Mô tả công việc"
          value={draft.description}
          onChange={(event) =>
            setDraft({ ...draft, description: event.target.value })
          }
        />
        <select
          aria-label={`${prefix} người nói`}
          value={draft.speakerId}
          onChange={(event) => {
            const speaker = meeting.speakers.find(
              (item) => item.id === event.target.value,
            )
            setDraft({
              ...draft,
              speakerId: speaker?.id ?? '',
              assigneeName: speaker?.name ?? draft.assigneeName,
            })
          }}
        >
          <option value="">Nhập tự do / chưa giao</option>
          {meeting.speakers.map((speaker) => (
            <option key={speaker.id} value={speaker.id}>
              {speaker.name}
            </option>
          ))}
        </select>
        <input
          aria-label={`${prefix} người phụ trách`}
          placeholder="Chưa giao"
          value={draft.assigneeName}
          onChange={(event) =>
            setDraft({
              ...draft,
              assigneeName: event.target.value,
              speakerId: '',
            })
          }
        />
        <input
          aria-label={`${prefix} hạn`}
          type="date"
          value={draft.dueDate}
          onChange={(event) =>
            setDraft({ ...draft, dueDate: event.target.value })
          }
        />
      </>
    )
  }

  if (query.isPending) return <div role="status">Đang tải công việc…</div>
  if (query.isError) return <div role="alert">Không tải được công việc.</div>

  const items = query.data.items ?? []
  return (
    <>
      <div className="notes-status">
        {items.filter((item) => item.status === 'open').length} việc cần làm ·{' '}
        {items.filter((item) => item.status === 'done').length} hoàn thành
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {conflict && (
        <div role="alertdialog" aria-label="Công việc đã thay đổi">
          <p>Công việc đã thay đổi ở nơi khác. Bản nháp vẫn được giữ.</p>
          <button onClick={() => window.location.reload()}>
            Tải lại trang
          </button>
          <button onClick={() => setConflict(false)}>Để sau</button>
        </div>
      )}
      <div className="tasks">
        {items.map((item) => (
          <div
            className={`task ${item.status === 'done' ? 'done' : ''}`}
            key={item.id}
          >
            <input
              type="checkbox"
              aria-label={`Hoàn thành: ${item.description}`}
              checked={item.status === 'done'}
              disabled={busy}
              onChange={() => void toggle(item)}
            />
            <div className="task-body">
              {editing === item.id ? (
                <form
                  onSubmit={(event) => {
                    event.preventDefault()
                    void update(item)
                  }}
                >
                  {fields('Sửa')}
                  <button type="submit" disabled={busy}>
                    Lưu công việc
                  </button>
                  <button type="button" onClick={() => setEditing(null)}>
                    Hủy
                  </button>
                </form>
              ) : (
                <>
                  <strong>{item.description}</strong>
                  <div className="task-meta">
                    <span>{item.assignee_name || 'Chưa giao'}</span>
                    <span>
                      {item.due_date
                        ? formatDate(item.due_date)
                        : 'Chưa có hạn'}
                    </span>
                    {item.due_date_text && (
                      <span>Gốc: {item.due_date_text}</span>
                    )}
                    <span>{item.source === 'ai' ? 'AI' : 'User'}</span>
                    {item.needs_review && <span>Cần kiểm tra</span>}
                    {item.is_edited && <span>Đã sửa</span>}
                  </div>
                  <button
                    aria-label={`Sửa công việc ${item.id}`}
                    onClick={() => {
                      setEditing(item.id)
                      setDraft(draftFrom(item))
                      setError('')
                    }}
                  >
                    Sửa
                  </button>
                  <button
                    aria-label={`Xóa công việc ${item.id}`}
                    onClick={() => void remove(item)}
                  >
                    Xóa
                  </button>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
      {!editing && (
        <form
          className="add-task"
          onSubmit={(event) => {
            event.preventDefault()
            void create()
          }}
        >
          {fields('Thêm')}
          <button type="submit" disabled={busy}>
            Thêm công việc
          </button>
        </form>
      )}
    </>
  )
}
