import { StrictMode } from 'react'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import * as api from '../../api/client'
import { AutosaveEditor } from './AutosaveEditor'

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})
function editor() {
  return render(
    <StrictMode>
      <AutosaveEditor
        meetingId="m"
        segmentId="s"
        text="Gốc"
        version={1}
        onSaved={() => {}}
        onClose={() => {}}
        onConflict={() => {}}
      />
    </StrictMode>,
  )
}

it('TC11 timer gộp phím, StrictMode không làm dừng autosave', async () => {
  vi.useFakeTimers()
  const patch = vi
    .spyOn(api, 'patchSegment')
    .mockResolvedValue({ text: 'C', version: 2 } as api.SegmentData)
  editor()
  const field = screen.getByRole('textbox')
  fireEvent.change(field, { target: { value: 'B' } })
  await act(() => vi.advanceTimersByTimeAsync(499))
  expect(patch).not.toHaveBeenCalled()
  fireEvent.change(field, { target: { value: 'C' } })
  await act(() => vi.advanceTimersByTimeAsync(499))
  expect(patch).not.toHaveBeenCalled()
  await act(() => vi.advanceTimersByTimeAsync(1))
  expect(patch).toHaveBeenCalledExactlyOnceWith('m', 's', {
    text: 'C',
    version: 1,
  })
  expect(screen.getByRole('status')).toHaveTextContent('Đã lưu')
})

it('TC12 unmount trước debounce không gửi request', async () => {
  vi.useFakeTimers()
  const patch = vi.spyOn(api, 'patchSegment')
  const view = editor()
  fireEvent.change(screen.getByRole('textbox'), {
    target: { value: 'Chưa lưu' },
  })
  view.unmount()
  await act(() => vi.advanceTimersByTimeAsync(1000))
  expect(patch).not.toHaveBeenCalled()
})

it('TC13 stale response không thay textbox; queue gửi C sau A', async () => {
  vi.useFakeTimers()
  let finish!: (data: api.SegmentData) => void
  const patch = vi
    .spyOn(api, 'patchSegment')
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    )
    .mockResolvedValueOnce({ text: 'C', version: 3 } as api.SegmentData)
  editor()
  const field = screen.getByRole('textbox')
  fireEvent.change(field, { target: { value: 'A' } })
  await act(() => vi.advanceTimersByTimeAsync(500))
  fireEvent.change(field, { target: { value: 'C' } })
  expect(field).toHaveValue('C')
  await act(async () => {
    finish({ text: 'A', version: 2 } as api.SegmentData)
  })
  expect(field).toHaveValue('C')
  expect(patch.mock.calls.map((call) => call[2])).toEqual([
    { text: 'A', version: 1 },
    { text: 'C', version: 2 },
  ])
})
