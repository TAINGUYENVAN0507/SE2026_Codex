import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listEdits } from '../../api/client'

const entityNames: Record<string, string> = {
  segment: 'Transcript',
  speaker: 'Người nói',
  summary: 'Tóm tắt',
  action_item: 'Công việc',
}

function formatValue(value: unknown) {
  if (value === null || value === undefined) return 'Không có'
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2)
}

function formatTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'Không rõ thời gian'
    : new Intl.DateTimeFormat('vi-VN', {
        dateStyle: 'short',
        timeStyle: 'short',
        timeZone: 'Asia/Ho_Chi_Minh',
      }).format(date)
}

export function HistoryPanel({ meetingId }: { meetingId: string }) {
  const [entityType, setEntityType] = useState('')
  const [page, setPage] = useState(1)
  const query = useQuery({
    queryKey: ['edits', meetingId, entityType, page],
    queryFn: () => listEdits(meetingId, page, entityType),
  })
  return (
    <section className="history-panel" aria-label="Lịch sử chỉnh sửa">
      <label className="history-filter">
        Loại thay đổi
        <select
          value={entityType}
          onChange={(event) => {
            setEntityType(event.target.value)
            setPage(1)
          }}
        >
          <option value="">Tất cả</option>
          {Object.entries(entityNames).map(([type, label]) => (
            <option value={type} key={type}>
              {label}
            </option>
          ))}
        </select>
      </label>
      {query.isPending ? (
        <p role="status">Đang tải lịch sử…</p>
      ) : query.isError ? (
        <div role="alert">
          <p>Không tải được lịch sử chỉnh sửa.</p>
          <button
            className="button quiet small"
            onClick={() => void query.refetch()}
          >
            Thử lại
          </button>
        </div>
      ) : (
        <>
          {!query.data.items?.length ? (
            <p className="empty-state compact">Chưa có chỉnh sửa phù hợp.</p>
          ) : (
            <ol className="history-list">
              {query.data.items.map((item) => (
                <li key={item.id}>
                  <header>
                    <strong>{item.actor.display_name}</strong>
                    <time dateTime={item.created_at}>
                      {formatTime(item.created_at)}
                    </time>
                  </header>
                  <p>
                    {entityNames[item.entity_type] || item.entity_type} ·{' '}
                    {item.field ||
                      { create: 'Thêm', delete: 'Xóa', update: 'Cập nhật' }[
                        item.action
                      ] ||
                      item.action}
                  </p>
                  <dl>
                    <div>
                      <dt>Trước</dt>
                      <dd>
                        <pre>{formatValue(item.before)}</pre>
                      </dd>
                    </div>
                    <div>
                      <dt>Sau</dt>
                      <dd>
                        <pre>{formatValue(item.after)}</pre>
                      </dd>
                    </div>
                  </dl>
                </li>
              ))}
            </ol>
          )}
          <nav className="history-pagination" aria-label="Phân trang lịch sử">
            <button
              className="button quiet small"
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
            >
              Trước
            </button>
            <span>
              Trang {page} · {query.data.total} thay đổi
            </span>
            <button
              className="button quiet small"
              disabled={page * 10 >= query.data.total}
              onClick={() => setPage(page + 1)}
            >
              Sau
            </button>
          </nav>
        </>
      )}
    </section>
  )
}
