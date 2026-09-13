import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom/vitest'
import { RecordUnsavedDialog } from './RecordUnsavedDialog'
afterEach(cleanup)
it('shows the actual dirty and invalid fields, focuses continue, and discards only on explicit action', async () => {
  const discard = vi.fn(), change = vi.fn()
  render(<RecordUnsavedDialog open title="R013 · 温室管理清单" dirtyFields={['标题', '摘要']} invalidFields={['标题']} onOpenChange={change} onDiscard={discard} />)
  expect(screen.getByRole('alertdialog')).toHaveTextContent('标题、摘要')
  expect(screen.getByRole('alertdialog')).toHaveClass('fixed')
  expect(screen.getByRole('alertdialog')).not.toHaveClass('relative')
  expect(screen.getByText('标题尚未通过校验，请继续编辑后保存。')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '继续编辑' })).toHaveFocus()
  await userEvent.keyboard('{Escape}'); expect(change).toHaveBeenCalledWith(false); expect(discard).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: '丢弃并离开' })); expect(discard).toHaveBeenCalledOnce()
})
it('does not invent field errors when only a valid draft is dirty', () => {
  render(<RecordUnsavedDialog open title="新增记录" dirtyFields={['标题']} invalidFields={[]} onOpenChange={vi.fn()} onDiscard={vi.fn()} />)
  expect(screen.queryByText(/尚未通过校验/)).not.toBeInTheDocument()
})
