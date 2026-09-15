import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { TaskDetail } from './TaskDetail'

afterEach(cleanup)
const detail = { automationName: '链接采集', nodeNames: { 'node-03': '读取页面' }, parameterDefinitions: [{ parameterId: 'p0', name: '零', description: '', type: 'number' as const, required: true }, { parameterId: 'pf', name: '开关', description: '', type: 'boolean' as const, required: true }, { parameterId: 'pn', name: '空值', description: '', type: 'string' as const, required: false }], task: { taskId: 'task-1', taskOrdinal: 49, projectId: 'project-1', batchId: 'batch-1', runId: 'run-1', runRequestId: 'request-1', status: 'failed', statusRevision: 2, inputSnapshotId: 'snapshot-1', createdAt: '2026-09-15T01:00:00Z', completedAt: '2026-09-15T01:01:00Z' }, inputSnapshot: { inputSnapshotId: 'snapshot-1', taskId: 'task-1', batchId: 'batch-1', parameters: { p0: 0, pf: false, pn: null }, inputs: [], capturedAt: '2026-09-15T01:00:00Z' }, run: { runId: 'run-1', runRequestId: 'request-1', status: 'failed', statusRevision: 2, executionGeneration: 1, preparedContentId: 'content-1', capabilityBindings: [], resourceRequest: {}, lastSequence: 4, terminal: true, error: { code: 'E_PAGE_TIMEOUT', message: '读取页面超时' }, startedAt: '2026-09-15T01:00:00Z', finishedAt: '2026-09-15T01:01:00Z' } }
const attempts = { items: [{ nodeVisitId: 'visit-1', nodeId: 'node-03', nodeName: '读取页面', attempt: 2, status: 'failed' as const, startedAt: '2026-09-15T01:00:20Z', completedAt: '2026-09-15T01:01:00Z', error: { code: 'E_PAGE_TIMEOUT' } }], page: 1, pageSize: 50, total: 1, sort: 'createdAt' }
const logs = { items: [{ runId: 'run-1', sequence: 3, eventId: 'event-3', executionGeneration: 1, nodeId: 'node-03', nodeVisitId: 'visit-1', attempt: 2, level: 'error' as const, message: '页面读取超时', occurredAt: '2026-09-15T01:01:00Z' }], afterSequence: 3, lastSequence: 4, hasMore: false }
const outputs = { items: [{ outputId: 'out-1', kind: 'value' as const, name: '计数', value: 0, runId: 'run-1', sequence: 2, nodeId: 'node-03', nodeVisitId: 'visit-1', attempt: 1, createdAt: '2026-09-15T01:00:10Z' }], page: 1, pageSize: 50, total: 1, sort: 'createdAt' }
const props = { detail, attempts, logs, outputs, selectedNode: null, level: null, query: '', loading: false, onTabChange: vi.fn(), onNodeChange: vi.fn(), onLevelChange: vi.fn(), onQueryChange: vi.fn(), onLoadMoreLogs: vi.fn(), onLoadMoreAttempts: vi.fn(), onLoadMoreOutputs: vi.fn(), onRetry: vi.fn(), onBack: vi.fn() }

it('shows the task header, persisted attempts and logs', () => {
  render(<TaskDetail {...props} selectedTab="logs"/>)
  expect(screen.getByRole('heading', { name: '任务 T0049' })).toBeVisible()
  expect(screen.getByText('自动化').parentElement).toHaveTextContent('链接采集')
  expect(screen.getByText('输入标识').parentElement).toHaveTextContent('参数任务')
  expect(screen.getByText('耗时').parentElement).toHaveTextContent('1 分钟')
  expect(screen.queryByText('task-1')).not.toBeInTheDocument()
  expect(screen.getByText('页面读取超时')).toBeVisible()
  expect(screen.getByText('尝试 2')).toBeVisible()
  expect(screen.getByText('读取页面')).toBeVisible()
  expect(screen.queryByText('node-03')).not.toBeInTheDocument()
  expect(screen.getByText('日志按持久序号连续读取。')).toBeVisible()
})

it('applies log search only on submit and clears it immediately', async () => {
  const onQueryChange = vi.fn(), user = userEvent.setup()
  const view = render(<TaskDetail {...props} selectedTab="logs" onQueryChange={onQueryChange}/>)
  await user.type(screen.getByRole('searchbox', { name: '搜索日志内容' }), '超时')
  expect(onQueryChange).not.toHaveBeenCalled()
  await user.keyboard('{Enter}')
  expect(onQueryChange).toHaveBeenCalledWith('超时')
  view.rerender(<TaskDetail {...props} query="超时" selectedTab="logs" onQueryChange={onQueryChange}/>)
  await user.click(screen.getByRole('button', { name: '清除日志搜索' }))
  expect(onQueryChange).toHaveBeenLastCalledWith('')
})

it('preserves typed null zero and false in the input snapshot', () => {
  render(<TaskDetail {...props} selectedTab="io"/>)
  expect(screen.getByText('零').closest('tr')).toHaveTextContent('0')
  expect(screen.getByText('开关').closest('tr')).toHaveTextContent('false')
  expect(screen.getByText('空值').closest('tr')).toHaveTextContent('null')
  expect(screen.queryByRole('button', { name: /查看截图|查看附件/ })).not.toBeInTheDocument()
  expect(screen.getByText('节点输出不代表任务最终业务成功。')).toBeVisible()
})

it('renders real failure facts without fake attachment actions', () => {
  render(<TaskDetail {...props} selectedTab="evidence"/>)
  expect(screen.getByRole('heading', { name: '读取页面超时' })).toBeVisible()
  expect(screen.getByRole('heading', { name: '错误记录' })).toBeVisible()
  expect(screen.getAllByText(/E_PAGE_TIMEOUT/)).toHaveLength(2)
  expect(screen.queryByRole('button', { name: /查看截图|查看附件/ })).not.toBeInTheDocument()
})

it('reports controlled tab selection', async () => {
  const onTabChange = vi.fn()
  render(<TaskDetail {...props} selectedTab="logs" onTabChange={onTabChange}/>)
  await userEvent.click(screen.getByRole('tab', { name: '输入与输出' }))
  expect(onTabChange).toHaveBeenCalledWith('io')
})

it('loads remaining attempts and outputs instead of silently truncating a page', async () => {
  const onLoadMoreAttempts = vi.fn(), onLoadMoreOutputs = vi.fn()
  const partial = { ...attempts, total: 2 }
  const { rerender } = render(<TaskDetail {...props} attempts={partial} selectedTab="logs" onLoadMoreAttempts={onLoadMoreAttempts}/>)
  await userEvent.click(screen.getByRole('button', { name: '加载更多尝试' }))
  expect(onLoadMoreAttempts).toHaveBeenCalledOnce()
  rerender(<TaskDetail {...props} outputs={{ ...outputs, total: 2 }} selectedTab="io" onLoadMoreOutputs={onLoadMoreOutputs}/>)
  await userEvent.click(screen.getByRole('button', { name: '加载更多输出' }))
  expect(onLoadMoreOutputs).toHaveBeenCalledOnce()
  rerender(<TaskDetail {...props} attempts={partial} selectedTab="evidence" onLoadMoreAttempts={onLoadMoreAttempts} loading/>)
  expect(screen.getByRole('button', { name: '加载更多尝试' })).toBeDisabled()
  rerender(<TaskDetail {...props} selectedTab="logs"/>)
  expect(screen.queryByRole('button', { name: '加载更多尝试' })).not.toBeInTheDocument()
})

it('does not report unknown or failed evidence reads as empty history', () => {
  const { rerender } = render(<TaskDetail {...props} outputs={undefined} selectedTab="io" error="读取失败"/>)
  expect(screen.getByRole('alert')).toHaveTextContent('读取失败')
  expect(screen.queryByText('没有节点输出。')).not.toBeInTheDocument()
  rerender(<TaskDetail {...props} attempts={undefined} selectedTab="logs" loading/>)
  expect(screen.queryByText('暂无节点尝试')).not.toBeInTheDocument()
  expect(screen.queryByText('没有匹配的日志。')).not.toBeInTheDocument()
  rerender(<TaskDetail {...props} logs={undefined} selectedTab="logs" error="日志搜索失败"/>)
  expect(screen.getByRole('alert')).toHaveTextContent('日志搜索失败')
  expect(screen.queryByText('没有匹配的日志。')).not.toBeInTheDocument()
  rerender(<TaskDetail {...props} outputs={{ ...outputs, items: [], total: 0 }} selectedTab="io"/>)
  expect(screen.getByText('没有节点输出。')).toBeVisible()
})

it('leads the evidence tab with errors and attempt history, without repeating inputs', async () => {
  const onLoadMoreAttempts = vi.fn()
  render(<TaskDetail {...props} attempts={{ ...attempts, total: 2 }} selectedTab="evidence" onLoadMoreAttempts={onLoadMoreAttempts}/>)
  expect(screen.getAllByRole('heading', { level: 3 })[0]).toHaveTextContent('读取页面超时')
  expect(screen.getByRole('heading', { name: '失败时页面截图' })).toBeVisible()
  expect(screen.getByRole('heading', { name: '历史尝试' })).toBeVisible()
  expect(screen.queryByRole('heading', { name: '运行时输入快照' })).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: '输出与产物' })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '加载更多尝试' }))
  expect(onLoadMoreAttempts).toHaveBeenCalledOnce()
})

it('uses Chinese task and attempt states with business and frozen names', () => {
  render(<TaskDetail {...props} detail={{ ...detail, task: { ...detail.task, status: 'timed_out' } }} selectedTab="logs"/>)
  expect(screen.getByText('已超时')).toBeVisible()
  expect(screen.getByText('失败')).toBeVisible()
  expect(screen.getByRole('heading', { name: '任务 T0049' })).toBeVisible()
  expect(screen.getByRole('button', { name: /读取页面/ })).toHaveAttribute('title', '读取页面')
})

it('falls back to task 1 and step when optional display fields are absent', () => {
  render(<TaskDetail {...props} attempts={{ ...attempts, items: [{ ...attempts.items[0], nodeName: '' }] }} detail={{ ...detail, nodeNames: undefined, task: { ...detail.task, taskOrdinal: null } }} selectedTab="logs"/>)
  expect(screen.getByRole('heading', { name: '任务 T0001' })).toBeVisible()
  expect(screen.getByText('步骤')).toBeVisible()
})
