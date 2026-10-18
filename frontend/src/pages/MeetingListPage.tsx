import { ArrowUpRightIcon } from '@phosphor-icons/react/dist/csr/ArrowUpRight'
import { FileTextIcon } from '@phosphor-icons/react/dist/csr/FileText'
import { MagnifyingGlassIcon } from '@phosphor-icons/react/dist/csr/MagnifyingGlass'
import { PlusIcon } from '@phosphor-icons/react/dist/csr/Plus'
import { SpinnerGapIcon } from '@phosphor-icons/react/dist/csr/SpinnerGap'
import { WarningCircleIcon } from '@phosphor-icons/react/dist/csr/WarningCircle'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Topbar } from '../components/Topbar'
import { useMeetings } from '../features/meetings/DemoStore'
import { formatDate, type MeetingStatus } from '../features/meetings/model'

const filters: { id: MeetingStatus | 'all'; label: string }[] = [
  { id: 'all', label: 'Tất cả' },
  { id: 'ready', label: 'Hoàn thành' },
  { id: 'processing', label: 'Đang xử lý' },
  { id: 'failed', label: 'Có lỗi' },
]

export function MeetingListPage() {
  const { meetings } = useMeetings()
  const [filter, setFilter] = useState<MeetingStatus | 'all'>('all')
  const [query, setQuery] = useState('')
  const filtered = useMemo(
    () =>
      meetings.filter(
        (m) =>
          (filter === 'all' || m.status === filter) &&
          m.title
            .toLocaleLowerCase('vi')
            .includes(query.trim().toLocaleLowerCase('vi')),
      ),
    [meetings, filter, query],
  )
  return (
    <>
      <Topbar />
      <main className="list-page">
        <div className="page-heading">
          <div className="title-line">
            <h1>Cuộc họp</h1>
            <span className="total-count">{meetings.length} cuộc họp</span>
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
                onClick={() => setFilter(f.id)}
              >
                {f.label}
                <span>
                  {f.id === 'all'
                    ? meetings.length
                    : meetings.filter((m) => m.status === f.id).length}
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
                {formatDate(m.date)}
                <small>{m.time}</small>
              </span>
              <span className="meeting-duration mono">
                {Math.floor(m.duration / 60)} phút
              </span>
              <span className="speaker-avatars">
                {m.speakers.length ? (
                  m.speakers.slice(0, 3).map((s, i) => (
                    <span
                      key={s.id}
                      className={`avatar ${i === 0 ? 'dark' : ''}`}
                      title={s.name}
                    >
                      {s.initials}
                    </span>
                  ))
                ) : (
                  <span className="muted">—</span>
                )}
              </span>
              <span className={`status-label ${m.status}`}>
                <i />
                {
                  {
                    ready: 'Đã hoàn thành',
                    processing: 'Đang tạo tóm tắt',
                    failed: 'Lỗi âm thanh',
                    pending: 'Chờ xử lý',
                  }[m.status]
                }
              </span>
              <ArrowUpRightIcon className="row-arrow" />
            </Link>
          ))}
          {!filtered.length && (
            <div className="empty-state">
              <MagnifyingGlassIcon size={28} />
              <h2>Không tìm thấy cuộc họp</h2>
              <p>Thử từ khóa khác hoặc chọn “Tất cả”.</p>
              <button
                className="button secondary"
                onClick={() => {
                  setQuery('')
                  setFilter('all')
                }}
              >
                Xóa bộ lọc
              </button>
            </div>
          )}
        </div>
        <p className="list-footer">
          Hiển thị {filtered.length} trên {meetings.length} cuộc họp
        </p>
      </main>
    </>
  )
}
