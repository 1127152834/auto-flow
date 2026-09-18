import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { ManualDirectory } from './ManualDirectory'

afterEach(cleanup)

const item = {
  manualItemId: 'manual-1',
  projectId: 'project-1',
  taskId: 'task-1',
  runId: 'run-1',
  instanceId: 'instance-1',
  checkpointRevision: 3,
  status: 'waiting',
  statusRevision: 1,
  expiresAt: new Date(Date.now() + 13 * 60_000).toISOString(),
  allowedTargets: [],
  resumeStarted: false,
  reason: '待确认页面内容',
  createdAt: '2026-09-18T00:00:00Z',
  updatedAt: '2026-09-18T00:00:00Z',
} as const

it('keeps the artboard columns and makes 进入人工处理 the primary row action', async () => {
  const user = userEvent.setup()
  const onOpen = vi.fn()
  const onResume = vi.fn()
  const onFinish = vi.fn()
  const onOpenTask = vi.fn()
  const onOpenBatch = vi.fn()
  render(<ManualDirectory items={[item as never]} onRetry={vi.fn()} onOpen={onOpen} onResume={onResume} onFinish={onFinish} onOpenTask={onOpenTask} onOpenBatch={onOpenBatch} />)
  for (const column of ['现场信息', '任务信息', '保留时间', '操作']) expect(screen.getByRole('columnheader', { name: column })).toBeVisible()
  expect(screen.getByText('等待处理')).toBeVisible()
  expect(screen.getByText('待确认页面内容')).toBeVisible()
  expect(screen.getByText('保留至', { exact: false })).toBeVisible()
  expect(screen.getByText('剩余 13 分钟')).toBeVisible()
  await user.click(screen.getByRole('button', { name: '进入人工处理' }))
  expect(onOpen).toHaveBeenCalledWith(item)
  await user.click(screen.getByRole('button', { name: '继续原任务' }))
  expect(onResume).toHaveBeenCalledWith(item)
  await user.click(screen.getByRole('button', { name: '明确结束' }))
  expect(onFinish).toHaveBeenCalledWith(item)
  await user.click(screen.getByRole('button', { name: '查看任务' }))
  expect(onOpenTask).toHaveBeenCalledWith('task-1')
  await user.click(screen.getByRole('button', { name: '查看批次' }))
  expect(onOpenBatch).toHaveBeenCalledWith('run-1')
})

it('keeps an expired scene readable and still separates empty from failed reads', () => {
  render(<ManualDirectory items={[{ ...item, status: 'expired', expiresAt: new Date(Date.now() - 60_000).toISOString() } as never]} onRetry={vi.fn()} onResume={vi.fn()} onFinish={vi.fn()} />)
  expect(screen.getByText('已超时')).toBeVisible()
  expect(screen.getByText('已超过保留时间')).toBeVisible()
  expect(screen.queryByRole('button', { name: '进入人工处理' })).not.toBeInTheDocument()
  cleanup()
  render(<ManualDirectory items={[]} error="读取失败" onRetry={vi.fn()} onResume={vi.fn()} onFinish={vi.fn()} />)
  expect(screen.getByRole('alert')).toHaveTextContent('读取失败')
  expect(screen.queryByText('当前没有等待人工处理的环境。')).not.toBeInTheDocument()
  cleanup()
  render(<ManualDirectory items={[]} onRetry={vi.fn()} onResume={vi.fn()} onFinish={vi.fn()} />)
  expect(screen.getByText('当前没有等待人工处理的环境。')).toBeVisible()
})
