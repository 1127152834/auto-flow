import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom/vitest'
import { createRef } from 'react'
import { Button } from './button'
import { IconButton } from './icon-button'
afterEach(cleanup)
it('loading prevents duplicate actions and keeps its name', async () => {
  const user = userEvent.setup(), action = vi.fn()
  render(<Button loading onClick={action}>保存配置</Button>)
  const button = screen.getByRole('button', { name: '保存配置' })
  expect(button).toHaveAttribute('aria-busy', 'true')
  expect(button).toBeDisabled()
  await user.click(button)
  expect(action).not.toHaveBeenCalled()
})
it('defaults to a non-submit action and supports explicit submit and ref', async () => {
  const user = userEvent.setup(), submit = vi.fn(e => e.preventDefault()), ref = createRef<HTMLButtonElement>()
  render(<form onSubmit={submit}><Button ref={ref}>普通操作</Button><Button type="submit">提交</Button></form>)
  await user.click(screen.getByRole('button', { name: '普通操作' }))
  expect(submit).not.toHaveBeenCalled()
  expect(ref.current).toBe(screen.getByRole('button', { name: '普通操作' }))
  await user.click(screen.getByRole('button', { name: '提交' }))
  expect(submit).toHaveBeenCalledTimes(1)
})
it('loadingText is visible without removing the original accessible name', () => {
  render(<Button loading loadingText="正在保存…">保存配置</Button>)
  expect(screen.getByRole('button', { name: '保存配置' })).toHaveTextContent('正在保存…')
})
it('IconButton keeps its explicit accessible name while loading', () => {
  render(<IconButton aria-label="刷新目录" loading><span aria-hidden>↻</span></IconButton>)
  expect(screen.getByRole('button', { name: '刷新目录' })).toBeDisabled()
})
