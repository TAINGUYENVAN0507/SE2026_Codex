import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { EvidenceLinks } from './EvidenceLinks'
import type { Segment } from './model'

const segments: Segment[] = [
  {
    id: 'e1',
    start: 37.25,
    end: 42,
    text: 'Dẫn chứng tổng hợp',
    originalText: 'Dẫn chứng tổng hợp',
    speakerId: null,
    edited: false,
  },
]

it('seeks to the exact segment time when evidence is clicked', async () => {
  const onSeek = vi.fn()
  render(
    <EvidenceLinks ids={['e1', 'e1']} segments={segments} onSeek={onSeek} />,
  )
  const buttons = screen.getAllByRole('button', { name: /Nghe bằng chứng/ })
  expect(buttons).toHaveLength(1)
  await userEvent.click(buttons[0])
  expect(onSeek).toHaveBeenCalledWith(37.25)
  expect(screen.queryByText('Chưa có bằng chứng')).not.toBeInTheDocument()
})

it.each([undefined, [], ['missing']])(
  'shows the unverified label for %j',
  (ids) => {
    render(<EvidenceLinks ids={ids} segments={segments} onSeek={vi.fn()} />)
    expect(screen.getByText('Chưa có bằng chứng')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  },
)

it('keeps valid links while flagging a missing reference', () => {
  render(
    <EvidenceLinks
      ids={['e1', 'missing']}
      segments={segments}
      onSeek={vi.fn()}
    />,
  )
  expect(screen.getByRole('button')).toBeInTheDocument()
  expect(screen.getByText('Chưa có bằng chứng')).toBeInTheDocument()
})
