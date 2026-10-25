import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../../api/errors'
import {
  getSummary,
  putSummary,
  retrySummary,
  type SummaryData,
} from '../../api/client'
import type { Meeting } from './model'
import { formatTranscriptTime } from './transcriptUtils'
import { LoadingSkeleton } from '../../components/LoadingSkeleton'

type Content = NonNullable<SummaryData['content']>

function editableContent(content: Content): Content {
  return {
    overview: content.overview,
    key_points: (content.key_points ?? []).map((point) => ({ ...point })),
    decisions: (content.decisions ?? []).map((point) => ({ ...point })),
  }
}

export function RemoteSummary({
  meeting,
  onSeek,
}: {
  meeting: Meeting
  onSeek: (seconds: number) => void
}) {
  const queryClient = useQueryClient()
  const queryKey = ['summary', meeting.id]
  const query = useQuery({
    queryKey,
    queryFn: () => getSummary(meeting.id),
    refetchInterval: (current) =>
      current.state.data?.status === 'pending' ? 5000 : false,
  })
  const [draft, setDraft] = useState<Content | null>(null)
  const [error, setError] = useState('')
  const [conflict, setConflict] = useState(false)
  const [saving, setSaving] = useState(false)
  const [retrying, setRetrying] = useState(false)

  async function save() {
    if (!draft || !query.data) return
    const content = {
      ...draft,
      overview: draft.overview.trim(),
      key_points: (draft.key_points ?? []).map((point) => ({
        ...point,
        text: point.text.trim(),
      })),
      decisions: (draft.decisions ?? []).map((point) => ({
        ...point,
        text: point.text.trim(),
      })),
    }
    if (
      !content.overview ||
      content.overview.length > 5000 ||
      [...(content.key_points ?? []), ...(content.decisions ?? [])].some(
        (point) => !point.text,
      )
    ) {
      setError('Tổng quan và mỗi ý cần có nội dung hợp lệ.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const saved = await putSummary(meeting.id, {
        content,
        version: query.data.version,
      })
      queryClient.setQueryData(queryKey, saved)
      setDraft(null)
    } catch (cause) {
      if (cause instanceof ApiError && cause.code === 'VERSION_CONFLICT')
        setConflict(true)
      else
        setError(
          cause instanceof ApiError
            ? cause.message
            : 'Không thể lưu tóm tắt. Hãy thử lại.',
        )
    } finally {
      setSaving(false)
    }
  }

  function evidence(ids: string[] | undefined) {
    return ids?.map((id) => {
      const segment = meeting.segments.find((item) => item.id === id)
      return segment ? (
        <button
          key={id}
          className="evidence"
          aria-label={`Nghe bằng chứng từ ${formatTranscriptTime(segment.start)}`}
          onClick={() => onSeek(segment.start)}
        >
          {formatTranscriptTime(segment.start)} ↗
        </button>
      ) : null
    })
  }

  if (query.isPending)
    return <LoadingSkeleton kind="summary" label="Đang tải tóm tắt…" />
  if (query.isError)
    return (
      <div role="alert">
        Không tải được tóm tắt.{' '}
        <button onClick={() => void query.refetch()}>Thử lại</button>
      </div>
    )

  const summary = query.data
  if (summary.status === 'pending')
    return <LoadingSkeleton kind="summary" label="Đang tạo tóm tắt…" />
  if (summary.status !== 'ready' || !summary.content) {
    const descriptions: Record<string, string> = {
      pending: 'Đang tạo tóm tắt…',
      failed: 'Tạo tóm tắt thất bại.',
      insufficient_content: 'Nội dung cuộc họp chưa đủ để tạo tóm tắt.',
      disabled: 'Tính năng tóm tắt hiện chưa được bật.',
    }
    return (
      <div className="empty-state compact" role="status">
        <p>{descriptions[summary.status] ?? 'Chưa có bản tóm tắt.'}</p>
        {summary.status === 'failed' && (
          <button
            disabled={retrying}
            onClick={async () => {
              setRetrying(true)
              try {
                await retrySummary(meeting.id)
                await query.refetch()
              } catch (cause) {
                setError(
                  cause instanceof ApiError
                    ? cause.message
                    : 'Không thể tạo lại tóm tắt.',
                )
              } finally {
                setRetrying(false)
              }
            }}
          >
            Tạo lại tóm tắt
          </button>
        )}
        {error && <p role="alert">{error}</p>}
      </div>
    )
  }

  const content = draft ?? summary.content
  return (
    <>
      <div className="notes-status">
        <span>Bản tóm tắt · {summary.is_edited ? 'Đã sửa' : 'AI'}</span>
        {draft ? (
          <span>
            <button onClick={() => setDraft(null)}>Hủy</button>{' '}
            <button disabled={saving} onClick={() => void save()}>
              Lưu
            </button>
          </span>
        ) : (
          <button
            className="button quiet small"
            onClick={() => setDraft(editableContent(summary.content!))}
          >
            Chỉnh sửa
          </button>
        )}
      </div>
      {error && <p role="alert">{error}</p>}
      {conflict && (
        <div role="alertdialog" aria-label="Tóm tắt đã thay đổi">
          <p>Tóm tắt đã thay đổi ở nơi khác. Chữ đang sửa vẫn được giữ.</p>
          <button onClick={() => window.location.reload()}>
            Tải lại trang
          </button>
          <button onClick={() => setConflict(false)}>Để sau</button>
        </div>
      )}
      <section className="note-section">
        <h2>Tổng quan</h2>
        {draft ? (
          <textarea
            aria-label="Chỉnh sửa tổng quan"
            className="summary-editor"
            value={content.overview}
            onChange={(event) =>
              setDraft({ ...draft, overview: event.target.value })
            }
          />
        ) : (
          <p>{content.overview}</p>
        )}
      </section>
      {(['key_points', 'decisions'] as const).map((field) => (
        <section className="note-section" key={field}>
          <h2>{field === 'key_points' ? 'Ý chính' : 'Quyết định'}</h2>
          {(content[field] ?? []).map((point, index) => (
            <div className="decision" key={`${field}-${index}`}>
              {draft ? (
                <>
                  <input
                    aria-label={`${field === 'key_points' ? 'Ý chính' : 'Quyết định'} ${index + 1}`}
                    value={point.text}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        [field]: (draft[field] ?? []).map((item, at) =>
                          at === index
                            ? { ...item, text: event.target.value }
                            : item,
                        ),
                      })
                    }
                  />
                  <button
                    aria-label={`Xóa ${field} ${index + 1}`}
                    onClick={() =>
                      setDraft({
                        ...draft,
                        [field]: (draft[field] ?? []).filter(
                          (_, at) => at !== index,
                        ),
                      })
                    }
                  >
                    Xóa
                  </button>
                </>
              ) : (
                <p>
                  {point.text} {evidence(point.evidence_segment_ids)}
                </p>
              )}
            </div>
          ))}
          {draft && (
            <button
              onClick={() =>
                setDraft({
                  ...draft,
                  [field]: [
                    ...(draft[field] ?? []),
                    { text: '', evidence_segment_ids: [] },
                  ],
                })
              }
            >
              Thêm {field === 'key_points' ? 'ý chính' : 'quyết định'}
            </button>
          )}
        </section>
      ))}
    </>
  )
}
