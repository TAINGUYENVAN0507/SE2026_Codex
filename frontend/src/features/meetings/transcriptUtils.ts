import type { Segment } from './model'

export function groupConsecutiveSegments(segments: Segment[]): Segment[][] {
  return segments.reduce<Segment[][]>((groups, segment) => {
    const last = groups.at(-1)
    if (last?.[0].speakerId === segment.speakerId) last.push(segment)
    else groups.push([segment])
    return groups
  }, [])
}

export function formatTranscriptTime(seconds: number) {
  const total = Math.max(0, Math.floor(seconds))
  return [Math.floor(total / 3600), Math.floor(total / 60) % 60, total % 60]
    .map((value) => String(value).padStart(2, '0'))
    .join(':')
}
