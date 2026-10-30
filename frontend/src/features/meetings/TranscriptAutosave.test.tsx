import { useState } from 'react'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import * as api from '../../api/client'
import type { Meeting } from './model'
import { Transcript } from './Transcript'

const meeting: Meeting = {
  id: 'vt019-meeting',
  title: 'Fixture tổng hợp',
  date: '',
  time: '',
  duration: 10,
  status: 'ready',
  speakers: [],
  overview: '',
  points: [],
  decisions: [],
  tasks: [],
  segments: [
    {
      id: 'vt019-segment',
      start: 0,
      end: 5,
      speakerId: null,
      version: 1,
      text: 'Bản gốc',
      originalText: 'Bản gốc',
      edited: false,
    },
  ],
}

function Harness() {
  const [data, setData] = useState(meeting)
  return (
    <Transcript
      meeting={data}
      position={0}
      onSeek={() => {}}
      onUpdate={(fn) => setData(fn)}
    />
  )
}

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

it('TC01 AC1 tự lưu sau debounce mà không cần bấm Lưu', async () => {
  vi.useFakeTimers()
  const patch = vi.spyOn(api, 'patchSegment').mockResolvedValue({
    id: 'vt019-segment',
    text: 'Bản nháp mới',
    version: 2,
    is_edited: true,
  } as api.SegmentData)
  render(<Harness />)
  fireEvent.click(
    screen.getByRole('button', { name: 'Sửa đoạn vt019-segment' }),
  )
  fireEvent.change(
    screen.getByRole('textbox', { name: 'Chỉnh sửa transcript' }),
    { target: { value: 'Bản nháp mới' } },
  )
  await act(() => vi.advanceTimersByTimeAsync(501))
  expect(patch).toHaveBeenCalledExactlyOnceWith(
    'vt019-meeting',
    'vt019-segment',
    { text: 'Bản nháp mới', version: 1 },
  )
  expect(
    screen.getByRole('textbox', { name: 'Chỉnh sửa transcript' }),
  ).toHaveValue('Bản nháp mới')
})
