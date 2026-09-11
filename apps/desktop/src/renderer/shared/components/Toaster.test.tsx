import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { act, cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom/vitest'
import { Toaster, notify } from './Toaster'

beforeEach(() => vi.useFakeTimers())
afterEach(() => { cleanup(); vi.useRealTimers() })

it('shows a toast and removes it after 2600ms', async () => {
  render(<Toaster />)
  act(() => { notify({ title: '已保存', tone: 'success' }) })
  expect(screen.getByRole('status')).toHaveTextContent('已保存')
  act(() => { vi.advanceTimersByTime(2599) })
  expect(screen.getByRole('status')).toBeInTheDocument()
  act(() => { vi.advanceTimersByTime(1) })
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})

it('supports dismissing a toast', async () => {
  vi.useRealTimers()
  const user = userEvent.setup()
  render(<Toaster />)
  act(() => { notify({ title: '失败', tone: 'error' }) })
  const toast = screen.getByRole('status')
  await user.click(screen.getByRole('button', { name: '关闭通知' }))
  expect(toast).not.toBeInTheDocument()
})
