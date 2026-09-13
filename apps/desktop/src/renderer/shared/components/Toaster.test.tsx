import { StrictMode } from 'react'
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
  expect(screen.getByRole('status')).toHaveClass('toast-exit')
  act(() => { vi.advanceTimersByTime(149) })
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

it('deduplicates an operation, bounds visible notices and restarts its lifetime', () => {
  render(<Toaster />)
  let first!: number, repeat!: number
  act(() => {
    first = notify({ title: '保存 A', tone: 'success', operationId: 'workspace:a' })
    notify({ title: '保存 B', tone: 'success' }); notify({ title: '保存 C', tone: 'success' }); notify({ title: '保存 D', tone: 'success' })
  })
  expect(screen.getAllByRole('status')).toHaveLength(3)
  expect(screen.getByText(/另有.*项操作已完成/)).toBeInTheDocument()
  act(() => vi.advanceTimersByTime(2000))
  act(() => { repeat = notify({ title: 'A 已核验', tone: 'success', operationId: 'workspace:a' }) })
  expect(repeat).toBe(first)
  act(() => vi.advanceTimersByTime(1000))
  expect(screen.getByText('A 已核验')).toBeInTheDocument()
  act(() => vi.advanceTimersByTime(1750))
  expect(screen.queryByText('A 已核验')).not.toBeInTheDocument()
})

it('never turns overflowing failures into a success and cleans up timers', () => {
  const view = render(<Toaster />)
  act(() => { for (let index = 0; index < 5; index++) notify({ title: `错误 ${index}`, tone: 'error' }) })
  expect(screen.getAllByRole('status')).toHaveLength(3)
  expect(screen.queryByText(/操作已完成/)).not.toBeInTheDocument()
  view.unmount()
  expect(vi.getTimerCount()).toBe(0)
})


it('survives Strict Mode and refreshing a toast during its exit without old timers deleting it', () => {
  let first!: number
  act(() => { first = notify({title:'挂载前通知', operationId:'strict:one'}) })
  const view = render(<StrictMode><Toaster /></StrictMode>)
  expect(screen.getByText('挂载前通知')).toBeInTheDocument()
  act(() => vi.advanceTimersByTime(2650))
  act(() => { expect(notify({title:'核验结果已更新',operationId:'strict:one'})).toBe(first) })
  act(() => vi.advanceTimersByTime(150))
  expect(screen.getByText('核验结果已更新')).toBeInTheDocument()
  view.unmount();expect(vi.getTimerCount()).toBe(0)
})
