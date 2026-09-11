import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { UnsavedChangesDialog } from './UnsavedChangesDialog'

afterEach(cleanup)

it('keeps editing when cancelled and discards only on the destructive action', async () => {
  const user = userEvent.setup()
  const onOpenChange = vi.fn()
  const onDiscard = vi.fn()
  const view = render(<UnsavedChangesDialog open onOpenChange={onOpenChange} onDiscard={onDiscard} />)
  expect(screen.getByRole('button', { name: '继续编辑' })).toHaveFocus()
  await user.click(screen.getByRole('button', { name: '继续编辑' }))
  expect(onOpenChange).toHaveBeenCalledWith(false)
  expect(onDiscard).not.toHaveBeenCalled()

  view.rerender(<UnsavedChangesDialog open onOpenChange={onOpenChange} onDiscard={onDiscard} />)
  await user.click(screen.getByRole('button', { name: '放弃修改' }))
  expect(onDiscard).toHaveBeenCalledTimes(1)
})
