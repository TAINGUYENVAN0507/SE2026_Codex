import { useRef, useState } from 'react'
import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AudioPlayer, type PlayerHandle } from '../audio/AudioPlayer'
import { seedMeetings } from './model'
import { Transcript } from './Transcript'

const file = new File(['audio'], 'sample.wav', { type: 'audio/wav' })
function Harness() {
  const [position, setPosition] = useState(0)
  const [meeting, setMeeting] = useState(seedMeetings()[0])
  const player = useRef<PlayerHandle>(null)
  return (
    <>
      <AudioPlayer
        file={file}
        duration={meeting.duration}
        onPosition={setPosition}
        onFile={() => {}}
        ref={player}
      />
      <Transcript
        meeting={meeting}
        position={position}
        onSeek={(seconds) => player.current?.seek(seconds)}
        onUpdate={(transform) => setMeeting((current) => transform(current))}
      />
    </>
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('FE-08 player and transcript sync', () => {
  it('does not pause or seek while typing a transcript, and enables shortcuts outside fields (FE-16)', async () => {
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: () => 'blob:test',
      revokeObjectURL: () => {},
    })
    vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined)
    vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
    render(<Harness />)
    const audio = document.querySelector('audio')!
    Object.defineProperty(audio, 'duration', {
      configurable: true,
      value: 1720,
    })
    fireEvent.loadedMetadata(audio)
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Phát audio' }))
    await user.click(screen.getByRole('button', { name: 'Sửa đoạn s0' }))
    const field = screen.getByRole('textbox', { name: 'Chỉnh sửa transcript' })
    await user.type(field, ' thêm nội dung')
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('button', { name: 'Tạm dừng' })).toBeInTheDocument()
    expect(audio.currentTime).toBe(0)
    fireEvent.keyDown(document.body, { key: 'ArrowRight' })
    expect(audio.currentTime).toBe(10)
    fireEvent.keyDown(field, { key: ' ' })
    expect(screen.getByRole('button', { name: 'Tạm dừng' })).toBeInTheDocument()
  })
  it('ignores shortcuts inside contenteditable regions (FE-16)', () => {
    vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
    render(
      <>
        <AudioPlayer duration={100} onPosition={() => {}} onFile={() => {}} />
        <div
          contentEditable
          suppressContentEditableWarning
          aria-label="Ghi chú"
        >
          Nội dung
        </div>
      </>,
    )
    fireEvent.keyDown(screen.getByLabelText('Ghi chú'), { key: 'ArrowLeft' })
    expect(screen.getByRole('slider', { name: 'Tua bản ghi' })).toHaveValue(
      '100',
    )
  })
  it('keeps the initial playhead within a short API recording (FE-16)', () => {
    vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
    render(
      <AudioPlayer duration={13.86} onPosition={() => {}} onFile={() => {}} />,
    )
    expect(document.querySelector('.waveform')).toHaveStyle('--progress: 100%')
    expect(document.querySelector('.play-time strong')).toHaveTextContent(
      '00:13',
    )
  })
  it('seeks on timestamp, tracks timeupdate and respects the follow switch', async () => {
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: () => 'blob:test',
      revokeObjectURL: () => {},
    })
    vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
    render(<Harness />)
    const audio = document.querySelector('audio')!
    Object.defineProperty(audio, 'duration', {
      configurable: true,
      value: 1720,
    })
    fireEvent.loadedMetadata(audio)
    const scroll = vi.spyOn(Element.prototype, 'scrollIntoView')
    await userEvent.click(
      screen.getByRole('button', { name: 'Nghe từ 00:10:20' }),
    )
    expect(audio.currentTime).toBe(620)
    expect(scroll).not.toHaveBeenCalled()
    audio.currentTime = 640
    fireEvent.timeUpdate(audio)
    expect(document.getElementById('segment-s4')).toHaveClass('active')
    await userEvent.click(
      screen.getByRole('checkbox', { name: 'Theo đoạn đang phát' }),
    )
    audio.currentTime = 950
    fireEvent.timeUpdate(audio)
    expect(document.getElementById('segment-s5')).toHaveClass('active')
    expect(scroll).toHaveBeenCalled()
    expect(
      within(
        screen.getByRole('region', { name: 'Player audio cuộc họp' }),
      ).getByRole('combobox', { name: 'Tốc độ phát' }),
    ).toHaveValue('1')
  })
})
