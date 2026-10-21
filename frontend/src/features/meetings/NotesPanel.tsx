import { useState } from 'react'
import { ArrowUpRightIcon } from '@phosphor-icons/react/dist/csr/ArrowUpRight'
import { CheckCircleIcon } from '@phosphor-icons/react/dist/csr/CheckCircle'
import { PencilSimpleIcon } from '@phosphor-icons/react/dist/csr/PencilSimple'
import { PlusIcon } from '@phosphor-icons/react/dist/csr/Plus'
import { TrashIcon } from '@phosphor-icons/react/dist/csr/Trash'
import { formatDate, formatTime, type Meeting } from './model'

export function NotesPanel({
  meeting,
  tab,
  setTab,
  onSeek,
  onUpdate,
}: {
  meeting: Meeting
  tab: 'summary' | 'tasks'
  setTab: (t: 'summary' | 'tasks') => void
  onSeek: (s: number) => void
  onUpdate: (f: (m: Meeting) => Meeting) => void
}) {
  const [editing, setEditing] = useState(false)
  const [overview, setOverview] = useState(meeting.overview)
  const [taskText, setTaskText] = useState('')
  const [taskError, setTaskError] = useState('')
  function evidence(id: string) {
    const s = meeting.segments.find((seg) => seg.id === id)
    return s ? (
      <button className="evidence" onClick={() => onSeek(s.start)}>
        {formatTime(s.start)}
        <ArrowUpRightIcon size={11} />
      </button>
    ) : null
  }
  return (
    <aside className="notes-panel">
      <div className="notes-tabs">
        <button
          className={tab === 'summary' ? 'selected' : ''}
          onClick={() => setTab('summary')}
          aria-pressed={tab === 'summary'}
        >
          Tóm tắt
        </button>
        <button
          className={tab === 'tasks' ? 'selected' : ''}
          onClick={() => setTab('tasks')}
          aria-pressed={tab === 'tasks'}
        >
          Công việc <span className="badge">{meeting.tasks.length}</span>
        </button>
      </div>
      <div className="notes-scroll">
        {tab === 'summary' ? (
          <>
            <div className="notes-status">
              <span>
                {meeting.overview
                  ? 'Bản tóm tắt · đã hoàn thành'
                  : 'Chưa có bản tóm tắt'}
              </span>
              {meeting.overview && (
                <button
                  className="button quiet small"
                  onClick={() => {
                    setOverview(meeting.overview)
                    setEditing(true)
                  }}
                >
                  <PencilSimpleIcon />
                  Chỉnh sửa
                </button>
              )}
            </div>
            {meeting.overview ? (
              <>
                <section className="note-section">
                  <h2>Tổng quan</h2>
                  {editing ? (
                    <form
                      onSubmit={(e) => {
                        e.preventDefault()
                        if (overview.trim()) {
                          onUpdate((m) => ({ ...m, overview: overview.trim() }))
                          setEditing(false)
                        }
                      }}
                    >
                      <textarea
                        autoFocus
                        className="summary-editor"
                        aria-label="Chỉnh sửa tổng quan"
                        value={overview}
                        onChange={(e) => setOverview(e.target.value)}
                        required
                        maxLength={5000}
                      />
                      <div className="editor-footer">
                        <span />
                        <div>
                          <button
                            className="button quiet small"
                            type="button"
                            onClick={() => setEditing(false)}
                          >
                            Hủy
                          </button>
                          <button
                            className="button primary small"
                            type="submit"
                            disabled={!overview.trim()}
                          >
                            Lưu
                          </button>
                        </div>
                      </div>
                    </form>
                  ) : (
                    <p>{meeting.overview}</p>
                  )}
                </section>
                <section className="note-section">
                  <h2>Ý chính</h2>
                  <ul>
                    {meeting.points.map((p) => (
                      <li key={p.segmentId}>
                        {p.text} {evidence(p.segmentId)}
                      </li>
                    ))}
                  </ul>
                </section>
                <section className="note-section">
                  <h2>Quyết định</h2>
                  {meeting.decisions.map((p) => (
                    <div className="decision" key={p.segmentId}>
                      <CheckCircleIcon size={18} />
                      <p>
                        {p.text} {evidence(p.segmentId)}
                      </p>
                    </div>
                  ))}
                </section>
              </>
            ) : (
              <div className="empty-state compact">
                <p>Bản tóm tắt sẽ hiển thị sau khi xử lý transcript.</p>
              </div>
            )}
          </>
        ) : (
          <>
            <div className="notes-status">
              <span>
                {meeting.tasks.filter((t) => !t.done).length} việc cần làm ·{' '}
                {meeting.tasks.filter((t) => t.done).length} hoàn thành
              </span>
            </div>
            <div className="tasks">
              {meeting.tasks.map((task) => (
                <div
                  className={`task ${task.done ? 'done' : ''}`}
                  key={task.id}
                >
                  <input
                    type="checkbox"
                    aria-label={`Hoàn thành: ${task.text}`}
                    checked={task.done}
                    onChange={(e) =>
                      onUpdate((m) => ({
                        ...m,
                        tasks: m.tasks.map((t) =>
                          t.id === task.id
                            ? { ...t, done: e.target.checked }
                            : t,
                        ),
                      }))
                    }
                  />
                  <div className="task-body">
                    <input
                      className="task-description"
                      aria-label={`Nội dung công việc ${task.id}`}
                      value={task.text}
                      maxLength={1000}
                      onChange={(e) =>
                        onUpdate((m) => ({
                          ...m,
                          tasks: m.tasks.map((t) =>
                            t.id === task.id
                              ? { ...t, text: e.target.value }
                              : t,
                          ),
                        }))
                      }
                      onBlur={() => {
                        if (!task.text.trim())
                          onUpdate((m) => ({
                            ...m,
                            tasks: m.tasks.map((t) =>
                              t.id === task.id
                                ? { ...t, text: 'Công việc chưa đặt tên' }
                                : t,
                            ),
                          }))
                      }}
                    />
                    <div className="task-meta">
                      <input
                        aria-label={`Người phụ trách ${task.id}`}
                        placeholder="Chưa giao"
                        value={task.assignee}
                        onChange={(e) =>
                          onUpdate((m) => ({
                            ...m,
                            tasks: m.tasks.map((t) =>
                              t.id === task.id
                                ? { ...t, assignee: e.target.value }
                                : t,
                            ),
                          }))
                        }
                        maxLength={50}
                      />
                      <label className="due-label">
                        <span>
                          {task.dueDate
                            ? formatDate(task.dueDate)
                            : 'Chưa có hạn'}
                        </span>
                        <input
                          aria-label={`Hạn công việc ${task.id}`}
                          type="date"
                          value={task.dueDate}
                          onChange={(e) =>
                            onUpdate((m) => ({
                              ...m,
                              tasks: m.tasks.map((t) =>
                                t.id === task.id
                                  ? { ...t, dueDate: e.target.value }
                                  : t,
                              ),
                            }))
                          }
                        />
                      </label>
                    </div>
                  </div>
                  <button
                    className="icon-button delete-task"
                    aria-label={`Xóa công việc ${task.id}`}
                    onClick={() => {
                      if (window.confirm('Xóa công việc này khỏi bản xem thử?'))
                        onUpdate((m) => ({
                          ...m,
                          tasks: m.tasks.filter((t) => t.id !== task.id),
                        }))
                    }}
                  >
                    <TrashIcon size={15} />
                  </button>
                </div>
              ))}
            </div>
            <form
              className="add-task"
              onSubmit={(e) => {
                e.preventDefault()
                if (!taskText.trim()) {
                  setTaskError('Nhập nội dung công việc.')
                  return
                }
                onUpdate((m) => ({
                  ...m,
                  tasks: [
                    ...m.tasks,
                    {
                      id: crypto.randomUUID(),
                      text: taskText.trim(),
                      assignee: '',
                      dueDate: '',
                      done: false,
                    },
                  ],
                }))
                setTaskText('')
                setTaskError('')
              }}
            >
              <input
                aria-label="Công việc mới"
                placeholder="Thêm một công việc…"
                value={taskText}
                onChange={(e) => setTaskText(e.target.value)}
                maxLength={1000}
              />
              <button className="icon-button" aria-label="Thêm công việc">
                <PlusIcon size={18} />
              </button>
            </form>
            {taskError && (
              <p className="form-error" role="alert">
                {taskError}
              </p>
            )}
          </>
        )}
      </div>
    </aside>
  )
}
