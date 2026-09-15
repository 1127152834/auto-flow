import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { BatchDetail } from './BatchDetail'
import { BatchDirectory } from './BatchDirectory'
import { TaskDirectory } from './TaskDirectory'

afterEach(cleanup)

const batch = { batchId: 'batch-1', projectId: 'project-1', automationId: 'automation-1', automationName: '资料整理', startOperationId: 'operation-1', status: 'completed', statusRevision: 2, managementRevision: 1, requestedCount: 3, createdTaskCount: 3, activeTaskCount: 0, createdAt: '2026-09-15T01:00:00Z', completedAt: '2026-09-15T01:03:00Z' }
const batchPage = { items: [batch], page: 1, pageSize: 50, total: 1, sort: '-createdAt' }
const task = { taskId: 'task-1', taskOrdinal: 1, projectId: 'project-1', batchId: 'batch-1', runId: 'run-1', runRequestId: 'request-1', status: 'failed', statusRevision: 2, inputSnapshotId: 'snapshot-1', createdAt: '2026-09-15T01:00:00Z', completedAt: '2026-09-15T01:01:00Z' }

describe('run directories', () => {
  it('renders persisted batches and opens the selected batch', async () => {
    const onOpen = vi.fn()
    render(<BatchDirectory page={batchPage} filters={{ q: null, automationId: null, status: null, period: null }} automationOptions={[{ id: 'automation-1', name: '资料整理' }]} onFiltersChange={vi.fn()} onPageChange={vi.fn()} onOpen={onOpen} onRetry={vi.fn()}/>)
    expect(screen.getByText('资料整理')).toBeInTheDocument()
    expect(screen.getByText('3 个任务')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '查看记录' }))
    expect(onOpen).toHaveBeenCalledWith(batch)
  })

  it('keeps stale directory content visible when refresh fails', () => {
    render(<BatchDirectory page={batchPage} filters={{ q: null, automationId: null, status: null, period: null }} error="连接中断" refreshing onFiltersChange={vi.fn()} onPageChange={vi.fn()} onOpen={vi.fn()} onRetry={vi.fn()}/>)
    expect(screen.getByRole('alert')).toHaveTextContent('当前显示上次读取的记录')
    expect(screen.getByText('资料整理')).toBeInTheDocument()
  })

  it('shows task status from the server value and opens it', async () => {
    const onOpen = vi.fn()
    render(<TaskDirectory page={{ items: [task], page: 1, pageSize: 50, total: 1, sort: '-createdAt' }} filters={{ q: null, batchId: null, status: null, period: null }} onFiltersChange={vi.fn()} onPageChange={vi.fn()} onOpen={onOpen} onRetry={vi.fn()}/>)
    expect(screen.getByText('失败')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '查看任务' }))
    expect(onOpen).toHaveBeenCalledWith(task)
  })

  it('applies directory search only when the user submits it', async () => {
    const onFiltersChange = vi.fn()
    render(<BatchDirectory page={batchPage} filters={{ q: null, automationId: null, status: null, period: null }} onFiltersChange={onFiltersChange} onPageChange={vi.fn()} onOpen={vi.fn()} onRetry={vi.fn()}/>)
    const user = userEvent.setup()
    await user.type(screen.getByRole('textbox', { name: '搜索批次' }), '资料整理')
    expect(onFiltersChange).not.toHaveBeenCalled()
    await user.keyboard('{Enter}')
    expect(onFiltersChange).toHaveBeenCalledWith({ q: '资料整理', automationId: null, status: null, period: null })
  })

  it('distinguishes a filtered empty result and can clear every filter', async () => {
    const onFiltersChange = vi.fn()
    render(<TaskDirectory page={{ items: [], page: 1, pageSize: 50, total: 0, sort: '-createdAt' }} filters={{ q: 'missing', batchId: 'batch-1', status: 'failed', period: '7d' }} onFiltersChange={onFiltersChange} onPageChange={vi.fn()} onOpen={vi.fn()} onRetry={vi.fn()}/>)
    expect(screen.getByText('没有匹配的任务')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '清除筛选' }))
    expect(onFiltersChange).toHaveBeenCalledWith({ q: null, batchId: null, status: null, period: null })
  })

  it('does not claim a completed batch with failures fully succeeded', () => {
    render(<BatchDetail detail={{ batch, statusCounts: { succeeded: 2, failed: 1 }, taskCount: 3, stopOperation: null, configurationSnapshot: { automation: { name: '资料整理', managementRevision: 7, parameterSchema: [{ parameterId: 'parameter-id', name: '关键词' }], environmentPolicy: { source: 'newFromProfile' } }, parameters: { 'parameter-id': '种植资料' }, maxTasks: 3, concurrency: 1, workflowRevision: 5, resourceRequest: { browser: 'none', modelProviderId: null } } }} onBack={vi.fn()}/>)
    expect(screen.getByRole('heading', { name: '资料整理' })).toBeVisible()
    expect(screen.getByText(/批次开始于/)).toBeVisible()
    expect(screen.getByText('耗时').parentElement).toHaveTextContent('3 分钟')
    expect(screen.getByText('结束原因').parentElement).toHaveTextContent('本批次任务已结束')
    expect(screen.getByRole('alert')).toHaveTextContent('1 个任务失败或异常')
    expect(screen.getByText('关键词').closest('tr')).toHaveTextContent('种植资料')
    expect(screen.getByText('并发数').closest('tr')).toHaveTextContent('1')
    expect(screen.queryByText('batch-1')).not.toBeInTheDocument()
    expect(document.querySelector('pre')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '停止批次' })).not.toBeInTheDocument()
  })

  it('uses the frozen automation and start time without exposing the internal identifier', () => {
    render(<BatchDetail detail={{ batch, statusCounts: { succeeded: 3 }, taskCount: 3, stopOperation: null, configurationSnapshot: {} }} onBack={vi.fn()}/>)
    expect(screen.getByRole('heading', { name: '资料整理' })).toBeVisible()
    expect(screen.getByText(/批次开始于/)).toBeVisible()
    expect(screen.queryByText('batch-1')).not.toBeInTheDocument()
  })

  it('renders stop actions only when admitted by props', () => {
    const running = { ...batch, status: 'running', completedAt: null, activeTaskCount: 2 }
    const { rerender } = render(<BatchDetail detail={{ batch: running, statusCounts: { running: 2 }, taskCount: 2, stopOperation: null, configurationSnapshot: {} }} onBack={vi.fn()}/>)
    expect(screen.queryByRole('button', { name: '停止批次' })).not.toBeInTheDocument()
    rerender(<BatchDetail detail={{ batch: running, statusCounts: { running: 2 }, taskCount: 2, stopOperation: null, configurationSnapshot: {} }} onBack={vi.fn()} onStop={vi.fn()} onForceStop={vi.fn()}/>)
    expect(screen.getByRole('button', { name: '停止批次' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '强制停止' })).toBeInTheDocument()
  })
})
