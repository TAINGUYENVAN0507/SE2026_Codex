import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useIdempotencyKey } from './useIdempotencyKey'

describe('useIdempotencyKey', () => {
  it('keeps the key when the same file rerenders for a retry', () => {
    const file = new File(['audio'], 'meeting.mp3')
    const { result, rerender } = renderHook(
      ({ selected }: { selected: File | null }) => useIdempotencyKey(selected),
      { initialProps: { selected: file as File | null } },
    )
    const firstKey = result.current

    rerender({ selected: file })

    expect(firstKey).toEqual(expect.any(String))
    expect(result.current).toBe(firstKey)
  })

  it('creates a new key when the selected file changes', () => {
    const firstFile = new File(['first'], 'first.mp3')
    const secondFile = new File(['second'], 'second.mp3')
    const { result, rerender } = renderHook(
      ({ selected }: { selected: File | null }) => useIdempotencyKey(selected),
      { initialProps: { selected: firstFile } },
    )
    const firstKey = result.current

    rerender({ selected: secondFile })

    expect(result.current).not.toBe(firstKey)
  })

  it('returns null when there is no selected file', () => {
    const file = new File(['audio'], 'meeting.mp3')
    const { result, rerender } = renderHook(
      ({ selected }: { selected: File | null }) => useIdempotencyKey(selected),
      { initialProps: { selected: file as File | null } },
    )

    act(() => rerender({ selected: null }))

    expect(result.current).toBeNull()
  })
})
