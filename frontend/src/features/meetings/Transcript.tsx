import { useEffect, useState } from 'react'
import { MagnifyingGlassIcon } from '@phosphor-icons/react/dist/csr/MagnifyingGlass'
import { PencilSimpleIcon } from '@phosphor-icons/react/dist/csr/PencilSimple'
import { CheckIcon } from '@phosphor-icons/react/dist/csr/Check'
import { XIcon } from '@phosphor-icons/react/dist/csr/X'
import { formatTime, type Meeting } from './model'

interface Props {
  meeting: Meeting
  position: number
  onSeek: (seconds: number) => void
  onUpdate: (transform: (m: Meeting) => Meeting) => void
}
function Highlight({ text, query }: { text: string; query: string }) {
  const needle = query.trim().toLocaleLowerCase('vi')
  if (!needle) return <>{text}</>
  const parts: React.ReactNode[] = []
  let start = 0
  let at = text.toLocaleLowerCase('vi').indexOf(needle)
  while (at >= 0) {
    parts.push(
      text.slice(start, at),
      <mark key={at}>{text.slice(at, at + needle.length)}</mark>,
    )
    start = at + needle.length
    at = text.toLocaleLowerCase('vi').indexOf(needle, start)
  }
  parts.push(text.slice(start))
  return <>{parts}</>
}
export function Transcript({ meeting, position, onSeek, onUpdate }: Props) {
  const [query, setQuery] = useState('')
  const [speaker, setSpeaker] = useState('all')
  const [editing, setEditing] = useState<string>()
  const [draft, setDraft] = useState('')
  const [error, setError] = useState('')
  const [showOriginal, setShowOriginal] = useState<string>()
  const [follow, setFollow] = useState(false)
  const visible = meeting.segments.filter(
    (s) =>
      (speaker === 'all' || s.speakerId === speaker) &&
      s.text
        .toLocaleLowerCase('vi')
        .includes(query.trim().toLocaleLowerCase('vi')),
  )
  const active = meeting.segments.find(
    (s) => position >= s.start && position < s.end,
  )?.id
  useEffect(() => {
    if (follow && active && !editing)
      document
        .getElementById(`segment-${active}`)
        ?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [active, follow, editing])
  function save(id: string) {
    if (!draft.trim()) {
      setError('Nội dung không được để trống.')
      return
    }
    onUpdate((m) => ({
      ...m,
      segments: m.segments.map((s) =>
        s.id === id
          ? {
              ...s,
              text: draft.trim(),
              edited: draft.trim() !== s.originalText,
            }
          : s,
      ),
    }))
    setEditing(undefined)
    setError('')
  }
  return (
    <section className="transcript-panel" aria-label="Transcript">
      <div className="transcript-toolbar">
        <label className="search-input">
          <MagnifyingGlassIcon />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Tìm trong transcript"
            placeholder="Tìm trong transcript…"
          />
          {query && <span className="search-count">{visible.length}</span>}
        </label>
        <label className="follow-control">
          <input
            type="checkbox"
            checked={follow}
            onChange={(e) => setFollow(e.target.checked)}
          />
          Theo đoạn đang phát
        </label>
      </div>
      <div className="transcript-scroll">
        <div
          className="speaker-filters"
          role="group"
          aria-label="Lọc người nói"
        >
          <button
            className={speaker === 'all' ? 'selected' : ''}
            aria-pressed={speaker === 'all'}
            onClick={() => setSpeaker('all')}
          >
            Tất cả
          </button>
          {meeting.speakers.map((p) => (
            <button
              key={p.id}
              className={speaker === p.id ? 'selected' : ''}
              aria-pressed={speaker === p.id}
              onClick={() => setSpeaker(p.id)}
            >
              {p.name}
            </button>
          ))}
        </div>
        {visible.map((s) => {
          const p = meeting.speakers.find((item) => item.id === s.speakerId)
          return (
            <article
              className={`segment ${active === s.id ? 'active' : ''} ${editing === s.id ? 'editing' : ''}`}
              id={`segment-${s.id}`}
              key={s.id}
            >
              <header className="segment-header">
                <span
                  className={`avatar square ${p?.id === 'vt' ? 'dark' : ''}`}
                >
                  {p?.initials || '?'}
                </span>
                <strong>{p?.name || 'Chưa xác định'}</strong>
                <button
                  className="timestamp"
                  onClick={() => onSeek(s.start)}
                  aria-label={`Nghe từ ${formatTime(s.start)}`}
                >
                  {formatTime(s.start)}
                </button>
                {active === s.id && (
                  <span className="playing-label">Đang chọn</span>
                )}
                {s.edited && <span className="edited-label">Đã sửa</span>}
                <div className="segment-actions">
                  <select
                    aria-label={`Người nói đoạn ${s.id}`}
                    value={s.speakerId || ''}
                    onChange={(e) =>
                      onUpdate((m) => ({
                        ...m,
                        segments: m.segments.map((seg) =>
                          seg.id === s.id
                            ? { ...seg, speakerId: e.target.value || null }
                            : seg,
                        ),
                      }))
                    }
                  >
                    <option value="">Chưa xác định</option>
                    {meeting.speakers.map((person) => (
                      <option key={person.id} value={person.id}>
                        {person.name}
                      </option>
                    ))}
                  </select>
                  <button
                    className="icon-button"
                    onClick={() => {
                      setEditing(s.id)
                      setDraft(s.text)
                      setError('')
                    }}
                    aria-label={`Sửa đoạn ${s.id}`}
                  >
                    <PencilSimpleIcon />
                  </button>
                </div>
              </header>
              {editing === s.id ? (
                <div className="segment-editor">
                  <textarea
                    autoFocus
                    aria-label="Chỉnh sửa transcript"
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    maxLength={5000}
                    onKeyDown={(e) => {
                      if (e.key === 'Escape') setEditing(undefined)
                      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey))
                        save(s.id)
                    }}
                  />
                  {error && (
                    <p className="form-error" role="alert">
                      {error}
                    </p>
                  )}
                  <div className="editor-footer">
                    <span>Ctrl + Enter để lưu</span>
                    <div>
                      <button
                        className="button quiet small"
                        onClick={() => setEditing(undefined)}
                      >
                        <XIcon />
                        Hủy
                      </button>
                      <button
                        className="button primary small"
                        onClick={() => save(s.id)}
                      >
                        <CheckIcon />
                        Lưu thay đổi
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  <p className="segment-text">
                    <Highlight text={s.text} query={query} />
                  </p>
                  {s.edited && (
                    <button
                      className="original-toggle"
                      onClick={() =>
                        setShowOriginal((v) => (v === s.id ? undefined : s.id))
                      }
                    >
                      {showOriginal === s.id ? 'Ẩn bản gốc' : 'Xem bản AI gốc'}
                    </button>
                  )}
                  {showOriginal === s.id && (
                    <p className="original-text">{s.originalText}</p>
                  )}
                </>
              )}
            </article>
          )
        })}
        {!visible.length && (
          <div className="empty-state">
            <h2>
              {meeting.segments.length
                ? 'Không tìm thấy đoạn phù hợp'
                : 'Chưa có transcript'}
            </h2>
            <p>
              {meeting.segments.length
                ? 'Thử từ khóa khác hoặc chọn tất cả người nói.'
                : 'Transcript sẽ xuất hiện khi cuộc họp được xử lý.'}
            </p>
          </div>
        )}
      </div>
    </section>
  )
}
