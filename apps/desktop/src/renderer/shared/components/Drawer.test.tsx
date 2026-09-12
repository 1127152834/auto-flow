import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, it, expect, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { Drawer } from './Drawer'
afterEach(cleanup)
it('uses the same modal focus and busy boundary in a side frame', async () => {
  const user = userEvent.setup(), close = vi.fn()
  render(<Drawer open onOpenChange={close} title="详情" closeDisabled><button>内容操作</button></Drawer>)
  expect(screen.getByRole('dialog')).toHaveAttribute('data-placement', 'drawer')
  await user.keyboard('{Escape}')
  expect(close).not.toHaveBeenCalled()
  expect(screen.getByRole('button', { name: '正在处理，请稍候' })).toBeDisabled()
})
