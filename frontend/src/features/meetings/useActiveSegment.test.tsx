import { renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { findActiveSegment, useActiveSegment } from './useActiveSegment'

const segments = [
  { id: 'first', start_sec: 1, end_sec: 3 },
  { id: 'second', start_sec: 5, end_sec: 8 },
] as const

describe('active audio segment', () => {
  it('returns null for empty input, silence, and outside the transcript', () => {
    expect(findActiveSegment([], 1)).toBeNull()
    expect(findActiveSegment(segments, 0)).toBeNull()
    expect(findActiveSegment(segments, 4)).toBeNull()
    expect(findActiveSegment(segments, 9)).toBeNull()
    expect(findActiveSegment(segments, Number.NaN)).toBeNull()
  })

  it('includes start_sec and excludes end_sec', () => {
    expect(findActiveSegment(segments, 1)?.id).toBe('first')
    expect(findActiveSegment(segments, 2.999)?.id).toBe('first')
    expect(findActiveSegment(segments, 3)).toBeNull()
    expect(findActiveSegment(segments, 5)?.id).toBe('second')
    expect(findActiveSegment(segments, 8)).toBeNull()
  })

  it('chooses the latest-started active segment during overlap', () => {
    const overlapping = [
      { id: 'long', start_sec: 0, end_sec: 10, overlap: true },
      { id: 'short', start_sec: 3, end_sec: 4, overlap: true },
      { id: 'late', start_sec: 5, end_sec: 6 },
    ]
    expect(findActiveSegment(overlapping, 3.5)?.id).toBe('short')
    expect(findActiveSegment(overlapping, 4)?.id).toBe('long')
    expect(findActiveSegment(overlapping, 5.5)?.id).toBe('late')
    expect(findActiveSegment(overlapping, 6)?.id).toBe('long')
  })

  it('updates the hook when playback time changes', () => {
    const { result, rerender } = renderHook(
      ({ currentTime }) => useActiveSegment(segments, currentTime),
      { initialProps: { currentTime: 1 } },
    )
    expect(result.current?.id).toBe('first')
    rerender({ currentTime: 4 })
    expect(result.current).toBeNull()
    rerender({ currentTime: 5 })
    expect(result.current?.id).toBe('second')
  })

  it('finds a segment efficiently in a thousand sorted segments', () => {
    const many = Array.from({ length: 1_000 }, (_, index) => ({
      id: index,
      start_sec: index * 2,
      end_sec: index * 2 + 1,
    }))
    const started = performance.now()
    expect(findActiveSegment(many, 1_998.5)?.id).toBe(999)
    expect(performance.now() - started).toBeLessThan(100)
  })
})
