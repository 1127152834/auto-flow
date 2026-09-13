import { useState } from 'react'
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom/vitest'
import { Popover, PopoverTrigger, PopoverContent } from './popover'
import { Select } from './select'
import { Dialog, DialogTrigger, DialogContent, DialogTitle, DialogDescription } from './dialog'
import { choiceTestEnvironment } from '../../testing/choice-user'
choiceTestEnvironment()
afterEach(cleanup)
function Example() {
  const [open, setOpen] = useState(false)
  return <Dialog><DialogTrigger>打开表单</DialogTrigger><DialogContent><DialogTitle>表单</DialogTitle><DialogDescription>测试浮层</DialogDescription>
    <Popover open={open} onOpenChange={setOpen}><PopoverTrigger>筛选</PopoverTrigger><PopoverContent aria-label="筛选条件"><input aria-label="关键词" /><Select aria-label="字段" value="a" onValueChange={() => {}} options={[{ value: 'a', label: '标题' }, { value: 'b', label: '描述' }]} clearable={false} /></PopoverContent></Popover>
  </DialogContent></Dialog>
}
it('closes nested Select before Popover before Dialog and restores focus', async () => {
  const user = userEvent.setup(); render(<Example />)
  await user.click(screen.getByText('打开表单')); await user.click(screen.getByText('筛选'))
  expect(screen.getByLabelText('关键词')).toHaveFocus()
  await user.tab(); expect(screen.getByRole('combobox', { name: '字段' })).toHaveFocus(); await user.keyboard('{ArrowDown}')
  expect(screen.getByRole('listbox')).toBeInTheDocument()
  await user.keyboard('{Escape}')
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  expect(screen.getByLabelText('关键词')).toBeInTheDocument()
  await user.keyboard('{Escape}')
  expect(screen.queryByLabelText('关键词')).not.toBeInTheDocument()
  await waitFor(() => expect(screen.getByText('筛选')).toHaveFocus())
  expect(screen.getByRole('dialog', { name: '表单' })).toBeInTheDocument()
  await user.keyboard('{Escape}')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})
it('supports outside dismissal and constrains the scrolling surface to available space', async () => {
  const user = userEvent.setup()
  render(<><button>外部</button><Popover><PopoverTrigger>排序</PopoverTrigger><PopoverContent aria-label="排序内容"><input aria-label="排序输入" /></PopoverContent></Popover></>)
  await user.click(screen.getByText('排序'))
  expect(screen.getByRole('dialog')).toHaveClass('overflow-auto')
  await user.click(screen.getByText('外部'))
  expect(screen.queryByLabelText('排序输入')).not.toBeInTheDocument()
  await waitFor(() => expect(screen.getByText('排序')).toHaveFocus())
})
