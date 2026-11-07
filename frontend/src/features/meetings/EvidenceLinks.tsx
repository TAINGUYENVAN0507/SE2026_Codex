import { ArrowUpRightIcon } from '@phosphor-icons/react/dist/csr/ArrowUpRight'
import type { Meeting } from './model'
import { formatTranscriptTime } from './transcriptUtils'

export function EvidenceLinks({
  ids,
  segments,
  onSeek,
}: {
  ids?: string[]
  segments: Meeting['segments']
  onSeek: (seconds: number) => void
}) {
  const unique = [...new Set(ids ?? [])]
  const known = unique.flatMap((id) => {
    const segment = segments.find((item) => item.id === id)
    return segment ? [segment] : []
  })
  const missing = !unique.length || known.length < unique.length
  return (
    <span className="evidence-links">
      {known.map((segment) => (
        <button
          key={segment.id}
          type="button"
          className="evidence"
          aria-label={`Nghe bằng chứng từ ${formatTranscriptTime(segment.start)}`}
          onClick={() => onSeek(segment.start)}
        >
          {formatTranscriptTime(segment.start)}{' '}
          <ArrowUpRightIcon size={12} aria-hidden="true" />
        </button>
      ))}
      {missing && (
        <span className="unverified-evidence">Chưa có bằng chứng</span>
      )}
    </span>
  )
}
