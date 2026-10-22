import { ArrowUpRightIcon } from '@phosphor-icons/react/dist/csr/ArrowUpRight'
import { FileTextIcon } from '@phosphor-icons/react/dist/csr/FileText'
import { MagnifyingGlassIcon } from '@phosphor-icons/react/dist/csr/MagnifyingGlass'
import { PlusIcon } from '@phosphor-icons/react/dist/csr/Plus'
import { SpinnerGapIcon } from '@phosphor-icons/react/dist/csr/SpinnerGap'
import { WarningCircleIcon } from '@phosphor-icons/react/dist/csr/WarningCircle'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Topbar } from '../components/Topbar'
import { ApiError } from '../api/errors'
import type { MeetingDetail } from '../api/client'
import { useMeetingsQuery } from '../features/meetings/useMeetingsQuery'
import { formatDate } from '../features/meetings/model'

type Status = MeetingDetail['status']
const filters: { id: Status | 'all'; label: string }[] = [
  { id: 'all', label: 'Tất cả' },
  { id: 'ready', label: 'Hoàn thành' },
  { id: 'processing', label: 'Đang xử lý' },
  { id: 'queued', label: 'Chờ xử lý' },
  { id: 'partial', label: 'Một phần' },
  { id: 'failed', label: 'Có lỗi' },
]

export function MeetingListPage() {
  const [filter, setFilter] = useState<Status | 'all'>('all')
  const [page, setPage] = useState(1)
  const [query, setQuery] = useState('')
  const meetingsQuery = useMeetingsQuery({
    page,
    status: filter === 'all' ? undefined : filter,
  })
  const meetings = meetingsQuery.data?.items ?? []
  const filtered = meetings.filter((m) =>
    m.title
      .toLocaleLowerCase('vi')
      .includes(query.trim().toLocaleLowerCase('vi')),
  )
  return (
    <>
      <Topbar />
      <main className="list-page">
        <div className="page-heading">
          <div className="title-line">
            <h1>Cuộc họp</h1>
            <span className="total-count">
              {meetingsQuery.data?.total ?? 0} cuộc họp
            </span>
          </div>
          <Link className="button primary" to="/meetings/new">
            <PlusIcon />
            Cuộc họp mới
          </Link>
        </div>
        <div className="list-toolbar">
          <div className="filter-tabs" role="group" aria-label="Lọc trạng thái">
            {filters.map((f) => (
              <button
                key={f.id}
                className={filter === f.id ? 'selected' : ''}
                aria-pressed={filter === f.id}
                onClick={() => {
                  setFilter(f.id)
                  setPage(1)
                }}
              >
                {f.label}
                <span>
                  {f.id === filter ? (meetingsQuery.data?.total ?? 0) : ''}
                </span>
              </button>
            ))}
          </div>
          <label className="search-input">
            <MagnifyingGlassIcon />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Tìm theo tiêu đề cuộc họp…"
              aria-label="Tìm cuộc họp"
            />
          </label>
        </div>
        <div className="meeting-table">
          <div className="table-head" aria-hidden="true">
            <span>TIÊU ĐỀ CUỘC HỌP</span>
            <span>NGÀY TẠO</span>
            <span>THỜI LƯỢNG</span>
            <span>NGƯỜI NÓI</span>
            <span>TRẠNG THÁI</span>
            <span />
          </div>
          {meetingsQuery.isPending && (
            <div className="empty-state" role="status">
              Đang tải danh sách cuộc họp…
            </div>
          )}
          {meetingsQuery.isError && (
            <div className="empty-state" role="alert">
              <h2>Không tải được cuộc họp</h2>
              <p>
                {meetingsQuery.error instanceof ApiError
                  ? meetingsQuery.error.message
                  : 'Đã xảy ra lỗi. Hãy thử lại.'}
              </p>
              <button
                className="button secondary"
                onClick={() => void meetingsQuery.refetch()}
              >
                Thử lại
              </button>
            </div>
          )}
          {filtered.map((m) => (
            <Link key={m.id} className="meeting-row" to={`/meetings/${m.id}`}>
              <span className="meeting-name">
                {m.status === 'failed' ? (
                  <WarningCircleIcon className="error-color" />
                ) : m.status === 'processing' ? (
                  <SpinnerGapIcon className="accent-color" />
                ) : (
                  <FileTextIcon />
                )}
                <strong>{m.title}</strong>
              </span>
              <span className="meeting-date">
                {formatDate(m.meeting_date || m.created_at.slice(0, 10))}
                <small>
                  {new Date(m.created_at).toLocaleTimeString('vi-VN', {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </small>
              </span>
              <span className="meeting-duration mono">
                {m.duration_sec == null
                  ? '—'
                  : `${Math.floor(m.duration_sec / 60)} phút`}
              </span>
              <span className="speaker-avatars">
                {m.num_speakers_hint ?? <span className="muted">—</span>}
              </span>
              <span className={`status-label ${m.status}`}>
                <i />
                {
                  {
                    ready: 'Đã hoàn thành',
                    processing: 'Đang tạo tóm tắt',
                    failed: 'Lỗi âm thanh',
                    queued: 'Chờ xử lý',
                    partial: 'Hoàn thành một phần',
                  }[m.status]
                }
              </span>
              <ArrowUpRightIcon className="row-arrow" />
            </Link>
          ))}
          {meetingsQuery.isSuccess && !filtered.length && (
            <div className="empty-state">
              <MagnifyingGlassIcon size={28} />
              <h2>
                {meetings.length
                  ? 'Không tìm thấy cuộc họp'
                  : 'Chưa có cuộc họp'}
              </h2>
              <p>
                {meetings.length
                  ? 'Thử từ khóa khác hoặc chọn “Tất cả”.'
                  : 'Tạo cuộc họp mới để bắt đầu.'}
              </p>
              <button
                className="button secondary"
                onClick={() => {
                  setQuery('')
                  setFilter('all')
                  setPage(1)
                }}
              >
                Xóa bộ lọc
              </button>
            </div>
          )}
        </div>
        <p className="list-footer">
          Hiển thị {filtered.length} trên {meetingsQuery.data?.total ?? 0} cuộc
          họp
        </p>
        {(meetingsQuery.data?.total ?? 0) >
          (meetingsQuery.data?.page_size ?? 10) && (
          <nav aria-label="Phân trang cuộc họp">
            <button disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Trang trước
            </button>
            <span>Trang {page}</span>
            <button
              disabled={
                page * (meetingsQuery.data?.page_size ?? 10) >=
                (meetingsQuery.data?.total ?? 0)
              }
              onClick={() => setPage(page + 1)}
            >
              Trang sau
            </button>
          </nav>
        )}
      </main>
    </>
  )
}
