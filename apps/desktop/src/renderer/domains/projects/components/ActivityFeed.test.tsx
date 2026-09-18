import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { ActivityFeed } from './ActivityFeed'

afterEach(cleanup)

const item = { activityId: 'a1', kind: 'batch' as const, resource: { type: 'batch' as const, projectId: 'p', batchId: 'b1' }, summary: '批次完成', occurredAt: '2026-09-19T10:00:00Z' }

it('renders recorded facts and opens the target of the resource', async () => {
  const open = vi.fn()
  render(<ActivityFeed items={[item]} onOpen={open} />)
  expect(screen.getByText('批次完成')).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '打开' }))
  expect(open).toHaveBeenCalledWith({ tab: 'runs', batchId: 'b1' })
})

it('keeps the action visible but disabled when the object has no page', () => {
  render(<ActivityFeed items={[{ ...item, resource: { type: 'sync', projectId: 'p', tableId: 't1', syncOperationId: 's1' } }]} onOpen={vi.fn()} />)
  expect(screen.getByRole('button', { name: '打开' })).toBeDisabled()
})

it('says there is no activity yet and wraps a long summary instead of widening the page', () => {
  const long = '这是一条很长的活动摘要'.repeat(12)
  const { rerender } = render(<ActivityFeed items={[]} onOpen={vi.fn()} />)
  expect(screen.getByText('还没有运行或数据变更记录。')).toBeVisible()
  rerender(<ActivityFeed items={[{ ...item, summary: long }]} onOpen={vi.fn()} />)
  expect(screen.getByText(long)).toHaveClass('break-words')
})

it('separates the recorded in-flight work from the finished activity', () => {
  render(<ActivityFeed current={[{ ...item, activityId: 'live', summary: '批次处理中（running）' }]} items={[item]} onOpen={vi.fn()} />)
  const current = screen.getByRole('region', { name: '当前工作' })
  const recent = screen.getByRole('region', { name: '最近活动' })
  expect(current).toHaveTextContent('批次处理中（running）')
  expect(current).not.toHaveTextContent('批次完成')
  expect(recent).toHaveTextContent('批次完成')
  expect(recent).not.toHaveTextContent('批次处理中')
})

it('states that nothing is running instead of leaving the current group empty', () => {
  render(<ActivityFeed items={[]} onOpen={vi.fn()} />)
  expect(screen.getByRole('region', { name: '当前工作' })).toHaveTextContent('当前没有进行中的工作。')
})
