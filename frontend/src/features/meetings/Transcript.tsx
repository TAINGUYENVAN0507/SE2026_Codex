import { useEffect, useMemo, useState } from 'react'
import { MagnifyingGlassIcon } from '@phosphor-icons/react/dist/csr/MagnifyingGlass'
import { PencilSimpleIcon } from '@phosphor-icons/react/dist/csr/PencilSimple'
import { CheckIcon } from '@phosphor-icons/react/dist/csr/Check'
import { XIcon } from '@phosphor-icons/react/dist/csr/X'
import { type Meeting, type Segment } from './model'
import { useActiveSegment } from './useActiveSegment'
import { patchSegment, patchSpeaker } from '../../api/client'
import { ApiError } from '../../api/errors'
import { initials } from './model'
import {
  formatTranscriptTime,
  groupConsecutiveSegments,
} from './transcriptUtils'

interface Props {
  meeting: Meeting
  pending?: boolean
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
export function Transcript({
  meeting,
  pending = false,
  position,
  onSeek,
  onUpdate,
}: Props) {
  const [query, setQuery] = useState('')
  const [speaker, setSpeaker] = useState('all')
  const [editing, setEditing] = useState<string>()
  const [draft, setDraft] = useState('')
  const [error, setError] = useState('')
  const [showOriginal, setShowOriginal] = useState<string>()
  const [follow, setFollow] = useState(false)
  const [editingSpeaker, setEditingSpeaker] = useState<string>()
  const [speakerDraft, setSpeakerDraft] = useState('')
  const [speakerError, setSpeakerError] = useState('')
  const [versionConflict, setVersionConflict] = useState(false)
  const [savingSpeaker, setSavingSpeaker] = useState(false)
  const [savingSegment, setSavingSegment] = useState(false)
  const [segmentConflict, setSegmentConflict] = useState(false)
  const [aiOriginal, setAiOriginal] = useState(false)
  const shownSpeakerId = (s: Segment) =>
    aiOriginal && s.aiSpeakerId !== undefined ? s.aiSpeakerId : s.speakerId
  const visible = meeting.segments.filter(
    (s) =>
      (speaker === 'all' || shownSpeakerId(s) === speaker) &&
      (aiOriginal ? s.originalText : s.text)
        .toLocaleLowerCase('vi')
        .includes(query.trim().toLocaleLowerCase('vi')),
  )
  const groups = groupConsecutiveSegments(
    visible.map((s) => ({ ...s, speakerId: shownSpeakerId(s) })),
  )
  const timedSegments = useMemo(
    () =>
      meeting.segments.map((segment) => ({
        ...segment,
        start_sec: segment.start,
        end_sec: segment.end,
      })),
    [meeting.segments],
  )
  const active = useActiveSegment(timedSegments, position)?.id
  useEffect(() => {
    if (follow && active && !editing)
      document
        .getElementById(`segment-${active}`)
        ?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [active, follow, editing])
  async function save(id: string) {
    const text = draft.trim()
    if (text.length < 1 || text.length > 5000) {
      setError(
        text.length < 1
          ? 'Nội dung không được để trống.'
          : 'Nội dung không được quá 5000 ký tự.',
      )
      return
    }
    const previous = meeting.segments.find((segment) => segment.id === id)
    if (!previous || savingSegment) return
    setError('')
    setSavingSegment(true)
    onUpdate((m) => ({
      ...m,
      segments: m.segments.map((s) =>
        s.id === id
          ? {
              ...s,
              text,
              edited: text !== s.originalText,
            }
          : s,
      ),
    }))
    try {
      if (previous.version != null) {
        const saved = await patchSegment(meeting.id, id, {
          text,
          version: previous.version,
        })
        onUpdate((m) => ({
          ...m,
          segments: m.segments.map((s) =>
            s.id === id
              ? {
                  ...s,
                  text: saved.text,
                  edited: saved.is_edited,
                  version: saved.version,
                }
              : s,
          ),
        }))
      }
      setEditing(undefined)
    } catch (cause) {
      onUpdate((m) => ({
        ...m,
        segments: m.segments.map((s) => (s.id === id ? previous : s)),
      }))
      if (cause instanceof ApiError && cause.code === 'VERSION_CONFLICT')
        setSegmentConflict(true)
      else
        setError(
          cause instanceof ApiError
            ? cause.message
            : 'Không thể lưu đoạn transcript. Hãy thử lại.',
        )
    } finally {
      setSavingSegment(false)
    }
  }
  async function changeSpeaker(id: string, speakerId: string | null) {
    const previous = meeting.segments.find((segment) => segment.id === id)
    if (!previous || savingSegment) return
    setSavingSegment(true)
    setError('')
    onUpdate((m) => ({
      ...m,
      segments: m.segments.map((s) => (s.id === id ? { ...s, speakerId } : s)),
    }))
    try {
      if (previous.version != null) {
        const saved = await patchSegment(meeting.id, id, {
          speaker_id: speakerId,
          version: previous.version,
        })
        onUpdate((m) => ({
          ...m,
          segments: m.segments.map((s) =>
            s.id === id
              ? {
                  ...s,
                  speakerId: saved.speaker_id ?? null,
                  edited: saved.is_edited,
                  version: saved.version,
                }
              : s,
          ),
        }))
      }
    } catch (cause) {
      onUpdate((m) => ({
        ...m,
        segments: m.segments.map((s) => (s.id === id ? previous : s)),
      }))
      if (cause instanceof ApiError && cause.code === 'VERSION_CONFLICT')
        setSegmentConflict(true)
      else
        setError(
          cause instanceof ApiError
            ? cause.message
            : 'Không thể đổi người nói. Hãy thử lại.',
        )
    } finally {
      setSavingSegment(false)
    }
  }
  async function saveSpeaker() {
    const name = speakerDraft.trim()
    if (!editingSpeaker || !name || name.length > 50) {
      setSpeakerError('Tên người nói cần có từ 1 đến 50 ký tự.')
      return
    }
    const current = meeting.speakers.find((item) => item.id === editingSpeaker)
    if (!current) return
    setSpeakerError('')
    setSavingSpeaker(true)
    try {
      const saved =
        current.version == null
          ? { display_name: name, version: 1 }
          : await patchSpeaker(meeting.id, current.id, name, current.version)
      onUpdate((before) => ({
        ...before,
        speakers: before.speakers.map((speaker) =>
          speaker.id === current.id
            ? {
                ...speaker,
                name: saved.display_name,
                initials: initials(saved.display_name),
                version: saved.version,
              }
            : speaker,
        ),
      }))
      setEditingSpeaker(undefined)
    } catch (cause) {
      if (cause instanceof ApiError && cause.code === 'VERSION_CONFLICT')
        setVersionConflict(true)
      else if (
        cause instanceof ApiError &&
        cause.code === 'SPEAKER_NAME_DUPLICATE'
      )
        setSpeakerError('Tên người nói đã được sử dụng. Hãy chọn tên khác.')
      else
        setSpeakerError(
          cause instanceof ApiError
            ? cause.message
            : 'Không thể đổi tên người nói. Hãy thử lại.',
        )
    } finally {
      setSavingSpeaker(false)
    }
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
        <label className="follow-control">
          <input
            type="checkbox"
            checked={aiOriginal}
            onChange={(event) => setAiOriginal(event.target.checked)}
          />
          Bản AI gốc
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
            <div className="speaker-filter-item" key={p.id}>
              {editingSpeaker === p.id ? (
                <form
                  onSubmit={(event) => {
                    event.preventDefault()
                    void saveSpeaker()
                  }}
                >
                  <input
                    aria-label={`Tên mới của ${p.name}`}
                    value={speakerDraft}
                    maxLength={50}
                    onChange={(event) => setSpeakerDraft(event.target.value)}
                  />
                  <button type="submit" disabled={savingSpeaker}>
                    Lưu
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setEditingSpeaker(undefined)
                      setSpeakerError('')
                    }}
                  >
                    Hủy
                  </button>
                </form>
              ) : (
                <>
                  <button
                    className={speaker === p.id ? 'selected' : ''}
                    aria-pressed={speaker === p.id}
                    onClick={() => setSpeaker(p.id)}
                  >
                    {p.name}
                  </button>
                  <button
                    aria-label={`Đổi tên ${p.name}`}
                    onClick={() => {
                      setEditingSpeaker(p.id)
                      setSpeakerDraft(p.name)
                      setSpeakerError('')
                    }}
                  >
                    <PencilSimpleIcon size={13} />
                  </button>
                </>
              )}
            </div>
          ))}
        </div>
        {speakerError && (
          <p className="form-error" role="alert">
            {speakerError}
          </p>
        )}
        {versionConflict && (
          <div
            role="alertdialog"
            aria-label="Dữ liệu đã thay đổi"
            className="version-conflict"
          >
            <p>
              Dữ liệu người nói đã thay đổi ở nơi khác. Bạn có thể tải lại trang
              để cập nhật; tên đang gõ vẫn được giữ cho đến khi bạn chọn.
            </p>
            <button onClick={() => window.location.reload()}>
              Tải lại trang
            </button>
            <button onClick={() => setVersionConflict(false)}>Để sau</button>
          </div>
        )}
        {segmentConflict && (
          <div
            role="alertdialog"
            aria-label="Đoạn transcript đã thay đổi"
            className="version-conflict"
          >
            <p>
              Đoạn transcript đã thay đổi ở nơi khác. Hãy tải lại trang để cập
              nhật; chữ đang gõ vẫn được giữ cho đến khi bạn chọn.
            </p>
            <button onClick={() => window.location.reload()}>
              Tải lại trang
            </button>
            <button onClick={() => setSegmentConflict(false)}>Để sau</button>
          </div>
        )}
        {error && !editing && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {pending && (
          <div className="empty-state" role="status">
            <h2>Đang tạo transcript…</h2>
            <p>Transcript sẽ xuất hiện khi xử lý xong.</p>
            <div className="transcript-skeleton" aria-hidden="true" />
          </div>
        )}
        {groups.flatMap((group) =>
          group.map((s, index) => {
            const p = meeting.speakers.find((item) => item.id === s.speakerId)
            return (
              <article
                className={`segment ${index ? 'continuation' : 'group-start'} speaker-color-${p?.colorIndex ?? 'unknown'} ${active === s.id ? 'active' : ''} ${editing === s.id ? 'editing' : ''}`}
                id={`segment-${s.id}`}
                key={s.id}
              >
                <header className="segment-header">
                  {!index && (
                    <span
                      className={`avatar square ${p?.id === 'vt' ? 'dark' : ''}`}
                    >
                      {p?.initials || '?'}
                    </span>
                  )}
                  {!index && <strong>{p?.name || 'Chưa xác định'}</strong>}
                  <button
                    className="timestamp"
                    onClick={() => onSeek(s.start)}
                    aria-label={`Nghe từ ${formatTranscriptTime(s.start)}`}
                  >
                    {formatTranscriptTime(s.start)}
                  </button>
                  {s.flags?.includes('low_confidence') && (
                    <span className="transcript-flag">Cần nghe lại</span>
                  )}
                  {s.flags?.includes('overlap') && (
                    <span className="transcript-flag">Nói chồng</span>
                  )}
                  {active === s.id && (
                    <span className="playing-label">Đang chọn</span>
                  )}
                  {s.edited && !aiOriginal && (
                    <span className="edited-label">Đã sửa</span>
                  )}
                  {!aiOriginal && !pending && (
                    <div className="segment-actions">
                      <select
                        aria-label={`Người nói đoạn ${s.id}`}
                        value={s.speakerId || ''}
                        disabled={savingSegment}
                        onChange={(e) =>
                          void changeSpeaker(s.id, e.target.value || null)
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
                        disabled={savingSegment}
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
                  )}
                </header>
                {editing === s.id && !aiOriginal ? (
                  <div className="segment-editor">
                    <textarea
                      autoFocus
                      aria-label="Chỉnh sửa transcript"
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Escape') setEditing(undefined)
                        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                          e.preventDefault()
                          void save(s.id)
                        }
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
                          disabled={savingSegment}
                          onClick={() => void save(s.id)}
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
                      <Highlight
                        text={aiOriginal ? s.originalText : s.text}
                        query={query}
                      />
                    </p>
                    {s.edited && !aiOriginal && (
                      <button
                        className="original-toggle"
                        onClick={() =>
                          setShowOriginal((v) =>
                            v === s.id ? undefined : s.id,
                          )
                        }
                      >
                        {showOriginal === s.id
                          ? 'Ẩn bản gốc'
                          : 'Xem bản AI gốc'}
                      </button>
                    )}
                    {showOriginal === s.id && (
                      <p className="original-text">{s.originalText}</p>
                    )}
                  </>
                )}
              </article>
            )
          }),
        )}
        {!pending && !visible.length && (
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
