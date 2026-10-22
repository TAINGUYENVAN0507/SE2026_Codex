import { useMemo } from 'react'

export interface TimedSegment {
  start_sec: number
  end_sec: number
  overlap?: boolean
}

function prefixEnd<T extends TimedSegment>(segments: readonly T[]): number[] {
  let latestEnd = -Infinity
  return segments.map((segment) => {
    latestEnd = Math.max(latestEnd, segment.end_sec)
    return latestEnd
  })
}

function findInIndex<T extends TimedSegment>(
  segments: readonly T[],
  latestEnds: readonly number[],
  currentTime: number,
): T | null {
  if (!Number.isFinite(currentTime)) return null

  let low = 0
  let high = segments.length
  while (low < high) {
    const middle = Math.floor((low + high) / 2)
    if (segments[middle].start_sec <= currentTime) low = middle + 1
    else high = middle
  }

  // Duyệt ngược để ưu tiên đoạn bắt đầu muộn nhất khi có chồng lấn.
  for (let index = low - 1; index >= 0; index--) {
    if (latestEnds[index] <= currentTime) break
    if (currentTime < segments[index].end_sec) return segments[index]
  }
  return null
}

export function findActiveSegment<T extends TimedSegment>(
  segments: readonly T[],
  currentTime: number,
): T | null {
  return findInIndex(segments, prefixEnd(segments), currentTime)
}

export function useActiveSegment<T extends TimedSegment>(
  segments: readonly T[],
  currentTime: number,
): T | null {
  const latestEnds = useMemo(() => prefixEnd(segments), [segments])
  return findInIndex(segments, latestEnds, currentTime)
}
