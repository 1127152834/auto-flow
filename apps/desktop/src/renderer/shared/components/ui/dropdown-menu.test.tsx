import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from './dropdown-menu'

afterEach(cleanup)

it('opens from the keyboard, moves through items, and selects the focused action', async () => {
  const user = userEvent.setup()
  const onSelect = vi.fn()
  render(<DropdownMenu>
    <DropdownMenuTrigger>更多操作</DropdownMenuTrigger>
    <DropdownMenuContent>
      <DropdownMenuItem>编辑</DropdownMenuItem>
      <DropdownMenuSeparator />
      <DropdownMenuItem onSelect={onSelect}>删除</DropdownMenuItem>
    </DropdownMenuContent>
  </DropdownMenu>)

  screen.getByRole('button', { name: '更多操作' }).focus()
  await user.keyboard('{Enter}')
  expect(await screen.findByRole('menu')).toBeInTheDocument()
  await user.keyboard('{ArrowDown}{Enter}')
  expect(onSelect).toHaveBeenCalledOnce()
  await waitFor(() => expect(screen.queryByRole('menu')).not.toBeInTheDocument())
  expect(screen.getByRole('button', { name: '更多操作' })).toHaveFocus()
})
