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
const task = { taskId: 'task-1', taskOrdinal: 1, projectId: 'project-1', batchId: 'batch-1', runId: 'run-1', runRequestId: 'request-1', status: 'failed', statusRevision: 2, inputSnapshotId: 'snapshot-1', automationName: '资料整理', batchStartedAt: '2026-09-15T01:00:00Z', inputIdentifier: 'R001', endNodeName: '读取页面', createdAt: '2026-09-15T01:00:00Z', completedAt: '2026-09-15T01:01:00Z' }

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
    expect(screen.getByText('任务 1')).toBeInTheDocument()
    expect(screen.queryByText(/T0001/)).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '查看任务' }))
    expect(onOpen).toHaveBeenCalledWith(task)
  })

  it('uses the approved batch task columns without repeating the owning batch', () => {
    render(<TaskDirectory context="batch" page={{ items: [task], page: 1, pageSize: 50, total: 1, sort: '-createdAt' }} filters={{ q: null, batchId: 'batch-1', status: null, period: null }} batchOptions={[{ id: 'batch-1', name: '资料整理 · 09:00' }]} onFiltersChange={vi.fn()} onPageChange={vi.fn()} onOpen={vi.fn()} onRetry={vi.fn()}/>)
    expect(screen.getByRole('columnheader', { name: '输入标识' })).toBeVisible()
    expect(screen.getByRole('columnheader', { name: '结束节点' })).toBeVisible()
    expect(screen.getByRole('columnheader', { name: '结束时间' })).toBeVisible()
    expect(screen.queryByRole('columnheader', { name: '所属批次' })).not.toBeInTheDocument()
    expect(screen.getByText('R001')).toBeVisible()
    expect(screen.getByText('读取页面')).toBeVisible()
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
    render(<BatchDetail detail={{ batch, statusCounts: { succeeded: 2, failed: 1 }, taskCount: 3, reusedInputGroupCount: 0, unchangedInputStreak: 0, stopOperation: null, forceStopAllowed: false, forceStopAvailableAt: null, configurationSnapshot: { automation: { name: '资料整理', managementRevision: 7, parameterSchema: [{ parameterId: 'parameter-id', name: '关键词' }], environmentPolicy: { source: 'newFromProfile' } }, parameters: { 'parameter-id': '种植资料' }, maxTasks: 3, concurrency: 1, workflowRevision: 5, resourceRequest: { browser: 'none', modelProviderId: null } } }} onBack={vi.fn()}/>)
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
    render(<BatchDetail detail={{ batch, statusCounts: { succeeded: 3 }, taskCount: 3, reusedInputGroupCount: 2, unchangedInputStreak: 2, stopOperation: null, forceStopAllowed: false, forceStopAvailableAt: null, configurationSnapshot: {} }} onBack={vi.fn()}/>)
    expect(screen.getByRole('heading', { name: '资料整理' })).toBeVisible()
    expect(screen.getByText(/批次开始于/)).toBeVisible()
    expect(screen.queryByText('batch-1')).not.toBeInTheDocument()
    expect(screen.getByText(/已重复使用相同输入组 2 次/)).toHaveTextContent('当前输入条件连续 2 次未变化')
  })

  it('shows the affected input when a configuration failure drains and then fails', () => {
    const configuration = { automation: { inputPlan: { inputs: [{ inputId: 'mail', alias: '邮箱' }] } } }
    const failed = { ...batch, status: 'failed', selectionOutcome: { status: 'configurationError', issueInputIds: ['mail'] } }
    const { rerender } = render(<BatchDetail detail={{ batch: failed, statusCounts: { succeeded: 1 }, taskCount: 1, reusedInputGroupCount: 0, unchangedInputStreak: 0, stopOperation: null, forceStopAllowed: false, forceStopAvailableAt: null, configurationSnapshot: configuration }} onBack={vi.fn()}/>)
    expect(screen.getByText('结束原因').parentElement).toHaveTextContent('数据输入配置已失效：邮箱')
    rerender(<BatchDetail detail={{ batch: { ...failed, status: 'draining', completedAt: null }, statusCounts: { running: 1 }, taskCount: 1, reusedInputGroupCount: 0, unchangedInputStreak: 0, stopOperation: null, forceStopAllowed: false, forceStopAvailableAt: null, configurationSnapshot: configuration }} onBack={vi.fn()}/>)
    expect(screen.getByRole('status')).toHaveTextContent('邮箱')
    expect(screen.getByRole('status')).toHaveTextContent('等待已领取任务结束')
  })

  it('explains that candidate paging will continue without claiming exhaustion', () => {
    const waiting = {
      ...batch,
      status: 'blocked',
      completedAt: null,
      selectionOutcome: {
        status: 'scanBudgetExceeded',
        category: 'candidatePage',
        hasContinuation: true,
      },
    }
    render(<BatchDetail detail={{ batch: waiting, statusCounts: {}, taskCount: 0, reusedInputGroupCount: 0, unchangedInputStreak: 0, stopOperation: null, forceStopAllowed: false, forceStopAvailableAt: null, configurationSnapshot: {} }} onBack={vi.fn()}/>)
    expect(screen.getByRole('status')).toHaveTextContent('正在继续检查下一页候选数据')
    expect(screen.getByRole('status')).toHaveTextContent('尚未确认数据耗尽')
  })

  it('explains binding budget exhaustion without promising an automatic continuation', () => {
    const waiting = {
      ...batch,
      status: 'blocked',
      completedAt: null,
      selectionOutcome: {
        status: 'scanBudgetExceeded',
        category: 'candidateBindingBudget',
        hasContinuation: false,
      },
    }
    render(<BatchDetail detail={{ batch: waiting, statusCounts: {}, taskCount: 0, reusedInputGroupCount: 0, unchangedInputStreak: 0, stopOperation: null, forceStopAllowed: false, forceStopAvailableAt: null, configurationSnapshot: {} }} onBack={vi.fn()}/>)
    expect(screen.getByRole('status')).toHaveTextContent('候选组合检查预算已用完')
    expect(screen.getByRole('status')).toHaveTextContent('请收紧筛选或关联条件')
    expect(screen.getByRole('status')).not.toHaveTextContent('正在继续')
  })

  it.each([
    ['configurationError', '数据输入配置已失效'],
    ['ambiguous', '数据关联存在歧义'],
  ])('shows the affected alias and concrete issue for %s without making the internal id primary', (selectionStatus, message) => {
    const configuration = { automation: { inputPlan: { inputs: [{ inputId: 'input-mail-internal-id', alias: '邮箱' }] } } }
    const draining = {
      ...batch,
      status: 'draining',
      completedAt: null,
      selectionOutcome: {
        status: selectionStatus,
        issueInputIds: ['input-mail-internal-id'],
        issueDetails: { 'input-mail-internal-id': 'Selected field no longer exists.' },
      },
    }
    render(<BatchDetail detail={{ batch: draining, statusCounts: { running: 1 }, taskCount: 1, reusedInputGroupCount: 0, unchangedInputStreak: 0, stopOperation: null, forceStopAllowed: false, forceStopAvailableAt: null, configurationSnapshot: configuration }} onBack={vi.fn()}/>)
    expect(screen.getByRole('status')).toHaveTextContent(message)
    expect(screen.getByRole('status')).toHaveTextContent('邮箱：所选字段已不存在，请重新检查输入配置。')
    expect(screen.getByRole('status')).not.toHaveTextContent('Selected field no longer exists.')
    expect(screen.getByRole('status')).not.toHaveTextContent('input-mail-internal-id')
  })

  it('renders stop actions only when admitted by props', () => {
    const running = { ...batch, status: 'running', completedAt: null, activeTaskCount: 2 }
    const { rerender } = render(<BatchDetail detail={{ batch: running, statusCounts: { running: 2 }, taskCount: 2, reusedInputGroupCount: 0, unchangedInputStreak: 0, stopOperation: null, forceStopAllowed: false, forceStopAvailableAt: null, configurationSnapshot: {} }} onBack={vi.fn()}/>)
    expect(screen.queryByRole('button', { name: '停止批次' })).not.toBeInTheDocument()
    rerender(<BatchDetail detail={{ batch: running, statusCounts: { running: 2 }, taskCount: 2, reusedInputGroupCount: 0, unchangedInputStreak: 0, stopOperation: null, forceStopAllowed: false, forceStopAvailableAt: null, configurationSnapshot: {} }} onBack={vi.fn()} onStop={vi.fn()} onForceStop={vi.fn()}/>)
    expect(screen.getByRole('button', { name: '停止批次' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '强制停止' })).toBeInTheDocument()
  })
})

it.each([
  ['blocked', '尚未确认数据耗尽'],
  ['draining', '等待已领取任务结束'],
])('explains %s without inventing a completed result', (status, message) => {
  render(<BatchDetail detail={{ batch: { ...batch, status, completedAt: null }, statusCounts: {}, taskCount: 0, reusedInputGroupCount: 0, unchangedInputStreak: 0, stopOperation: null, forceStopAllowed: false, forceStopAvailableAt: null, configurationSnapshot: {} }} onBack={vi.fn()}/>)
  expect(screen.getByRole('status')).toHaveTextContent(message)
  expect(screen.getByText('结束原因').parentElement).toHaveTextContent('尚未结束')
})
