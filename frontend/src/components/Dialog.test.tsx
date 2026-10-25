import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { Dialog } from './Dialog'

function Harness() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button onClick={() => setOpen(true)}>Mở hộp thoại</button>
      {open && (
        <Dialog title="Có xung đột" onClose={() => setOpen(false)}>
          <button>Tải lại</button>
          <button onClick={() => setOpen(false)}>Để sau</button>
        </Dialog>
      )}
    </>
  )
}

describe('FE-16 dialog focus', () => {
  it('keeps Tab inside and returns focus to the trigger after Escape', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const trigger = screen.getByRole('button', { name: 'Mở hộp thoại' })
    await user.click(trigger)
    expect(screen.getByRole('alertdialog')).toHaveAttribute(
      'aria-modal',
      'true',
    )
    expect(screen.getByRole('button', { name: 'Tải lại' })).toHaveFocus()
    await user.tab({ shift: true })
    expect(screen.getByRole('button', { name: 'Để sau' })).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('button', { name: 'Tải lại' })).toHaveFocus()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })
})
