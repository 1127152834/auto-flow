import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { components } from '../../shared/api/generated'
import { BatchDetail } from '../project-runs/components/BatchDetail'
import { BatchDirectory } from '../project-runs/components/BatchDirectory'
import { StopBatchDialog } from '../project-runs/components/StopBatchDialog'
import { TaskDetail } from '../project-runs/components/TaskDetail'
import { TaskDirectory } from '../project-runs/components/TaskDirectory'
import { TaskEvidence } from '../project-runs/components/TaskEvidence'

type Schema = components['schemas']
const ids = {
  batch: '11111111-1111-4111-8111-111111111111', task1: '22222222-2222-4222-8222-222222222222',
  task2: '33333333-3333-4333-8333-333333333333', run: '44444444-4444-4444-8444-444444444444',
  request: '55555555-5555-4555-8555-555555555555', node: '66666666-6666-4666-8666-666666666666',
  visit: '77777777-7777-4777-8777-777777777777', parameter: '88888888-8888-4888-8888-888888888888',
  output: '99999999-9999-4999-8999-999999999999', content: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  automation: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', project: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
  operation: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd', snapshot: 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
}
const businessUuid = 'ffffffff-ffff-4fff-8fff-ffffffffffff'
const batch = { batchId: ids.batch, projectId: ids.project, automationId: ids.automation, automationName: '参数运行验收', startOperationId: ids.operation, status: 'running', statusRevision: 2, managementRevision: 3, requestedCount: 2, createdTaskCount: 2, activeTaskCount: 2, createdAt: '2026-09-15T04:41:00Z', completedAt: null } satisfies Schema['BatchView']
const task = (taskId: string, taskOrdinal: number) => ({ taskId, taskOrdinal, projectId: ids.project, batchId: ids.batch, runId: ids.run, runRequestId: ids.request, status: 'failed', statusRevision: 2, inputSnapshotId: ids.snapshot, createdAt: batch.createdAt, completedAt: '2026-09-15T04:42:00Z' }) satisfies Schema['TaskView']
const detail = {
  automationName: '参数运行验收', batchStartedAt: batch.createdAt, nodeNames: { [ids.node]: '冻结的读取页面' },
  parameterDefinitions: [{ parameterId: 'known-parameter', name: '业务参数', description: '', type: 'string' as const, required: false }],
  task: task(ids.task1, 1),
  inputSnapshot: { inputSnapshotId: ids.snapshot, taskId: ids.task1, batchId: ids.batch, parameters: { [ids.parameter]: businessUuid }, inputs: [], capturedAt: batch.createdAt },
  run: { runId: ids.run, runRequestId: ids.request, status: 'failed', statusRevision: 2, executionGeneration: 1, preparedContentId: ids.content, capabilityBindings: [], resourceRequest: {}, lastSequence: 1, terminal: true, error: { code: 'UNKNOWN_FAILURE', message: `failure ${ids.run}`, requestId: ids.request }, startedAt: '2026-09-15T04:42:00Z', finishedAt: '2026-09-15T04:42:00Z' },
} satisfies Schema['TaskDetail']
const attempt = { nodeVisitId: ids.visit, nodeId: ids.node, nodeName: '冻结的读取页面', attempt: 1, status: 'failed', startedAt: batch.createdAt, completedAt: '2026-09-15T04:42:00Z', error: { code: 'UNKNOWN_FAILURE', message: ids.node } } satisfies Schema['NodeAttemptView']
const output = { outputId: ids.output, kind: 'value', name: '业务输出', value: businessUuid, runId: ids.run, sequence: 1, nodeId: ids.node, nodeName: '冻结的读取页面', nodeVisitId: ids.visit, attempt: 1, createdAt: batch.createdAt } satisfies Schema['RunOutputView']
const hiddenIds = Object.values(ids)

function expectNoInternalIdentity() {
  for (const id of hiddenIds) {
    expect(document.body.textContent).not.toContain(id)
    for (const element of document.querySelectorAll('[title],[placeholder],[aria-label],[aria-description]')) {
      for (const attribute of ['title', 'placeholder', 'aria-label', 'aria-description']) expect(element.getAttribute(attribute) ?? '').not.toContain(id)
    }
  }
}

beforeEach(() => {
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
  HTMLElement.prototype.hasPointerCapture = vi.fn(() => false)
  HTMLElement.prototype.setPointerCapture = vi.fn()
  HTMLElement.prototype.releasePointerCapture = vi.fn()
  HTMLElement.prototype.scrollIntoView = vi.fn()
})
afterEach(cleanup)

describe('project run presentation identities', () => {
  it('shows batch names and start time in the required presentation', () => {
    render(<BatchDirectory page={{ items: [batch], page: 1, pageSize: 50, total: 1, sort: '-createdAt' }} filters={{ q: null, automationId: ids.automation, status: null, period: null }} automationOptions={[]} onFiltersChange={vi.fn()} onPageChange={vi.fn()} onOpen={vi.fn()} onRetry={vi.fn()} />)
    expect(screen.getByText('参数运行验收')).toBeVisible()
    const started = screen.getByText(/开始于/)
    expect(started).toHaveTextContent(/(?:9月15日|9\/15).*12:41/)
    expect(screen.getByPlaceholderText('搜索自动化名称')).toBeVisible()
  })

  it('keeps a stale automation choice semantic in the expanded select', async () => {
    render(<BatchDirectory filters={{ q: null, automationId: ids.automation, status: null, period: null }} automationOptions={[]} onFiltersChange={vi.fn()} onPageChange={vi.fn()} onOpen={vi.fn()} onRetry={vi.fn()} />)
    await userEvent.setup().click(screen.getByRole('combobox', { name: '自动化筛选' }))
    expect(screen.getByRole('option', { name: '自动化引用暂不可用' })).toBeVisible()
    expectNoInternalIdentity()
  })

  it('shows batch detail and tasks by business context and one-based ordinals', async () => {
    const first = render(<BatchDetail detail={{ batch, statusCounts: { running: 2 }, taskCount: 2, reusedInputGroupCount: 0, unchangedInputStreak: 0, stopOperation: null, forceStopAllowed: false, forceStopAvailableAt: null, configurationSnapshot: { automation: { name: '参数运行验收', parameterSchema: [{ parameterId: ids.parameter, name: '业务参数' }] }, parameters: { [ids.parameter]: businessUuid } } }} onBack={vi.fn()} />)
    expect(screen.getByRole('heading', { name: '参数运行验收' })).toBeVisible()
    expect(screen.getByText('业务参数').closest('tr')).toHaveTextContent(businessUuid)
    expectNoInternalIdentity()
    first.unmount()

    const user = userEvent.setup()
    render(<TaskDirectory page={{ items: [task(ids.task1, 1), task(ids.task2, 2)], page: 1, pageSize: 50, total: 2, sort: '-createdAt' }} filters={{ q: null, batchId: ids.batch, status: null, period: null }} batchOptions={[]} onFiltersChange={vi.fn()} onPageChange={vi.fn()} onOpen={vi.fn()} onRetry={vi.fn()} />)
    expect(screen.getByText('任务 1')).toBeVisible(); expect(screen.getByText('任务 2')).toBeVisible()
    expect(document.body.textContent).not.toMatch(/T0*001|T0*002/)
    expect(screen.getByPlaceholderText('搜索自动化名称或输入内容')).toBeVisible()
    await user.click(screen.getByRole('combobox', { name: '批次筛选' }))
    expect(screen.getByRole('option', { name: '批次资料暂不可用' })).toBeVisible()
    expectNoInternalIdentity()
  })

  it('uses frozen and semantic fallback node and parameter names while preserving business UUID values', async () => {
    const attempts = { items: [attempt, { ...attempt, nodeVisitId: ids.operation, nodeId: ids.operation, nodeName: '' }], page: 1, pageSize: 50, total: 2, sort: 'createdAt' }
    const view = render(<TaskDetail detail={detail} attempts={attempts} logs={{ items: [{ runId: ids.run, sequence: 1, eventId: ids.operation, executionGeneration: 1, nodeId: ids.node, nodeName: '冻结的读取页面', nodeVisitId: ids.visit, attempt: 1, level: 'error', message: '页面读取失败', occurredAt: batch.createdAt }], afterSequence: 1, lastSequence: 1, hasMore: false }} selectedTab="logs" selectedNode={null} level={null} query="" onTabChange={vi.fn()} onNodeChange={vi.fn()} onLevelChange={vi.fn()} onQueryChange={vi.fn()} onLoadMoreLogs={vi.fn()} onLoadMoreAttempts={vi.fn()} onLoadMoreOutputs={vi.fn()} onRetry={vi.fn()} onBack={vi.fn()} />)
    expect(screen.getByRole('heading', { name: '任务 1' })).toBeVisible()
    expect(screen.getByText(/开始于.*12:41/)).toBeVisible()
    expect(screen.getByText('冻结的读取页面')).toBeVisible(); expect(screen.getByText('未命名节点')).toBeVisible()
    await userEvent.setup().click(screen.getByRole('combobox', { name: '筛选日志节点' }))
    expect(screen.getByRole('option', { name: '冻结的读取页面' })).toBeVisible()
    expect(screen.getByRole('option', { name: '未命名节点' })).toBeVisible()
    expectNoInternalIdentity()
    view.unmount()

    const inputDetail: Schema['TaskDetail'] = { ...detail, inputSnapshot: { ...detail.inputSnapshot, inputs: [{ alias: '客户输入', records: [{ recordRef: { projectId: ids.project, tableId: ids.automation, datasetGeneration: ids.snapshot, recordKey: { type: 'uuid', value: ids.task2 } } }] }] } }
    render(<TaskEvidence mode="io" detail={inputDetail} outputs={{ items: [output], page: 1, pageSize: 50, total: 1, sort: 'createdAt' }} onLoadMoreAttempts={vi.fn()} onLoadMoreOutputs={vi.fn()} />)
    expect(screen.getByText('未知参数')).toBeVisible()
    expect(screen.getAllByText(businessUuid)).toHaveLength(2)
    expect(screen.getByText(/客户输入/)).toBeVisible()
    expectNoInternalIdentity()
  })

  it.each([
    ['uses the frozen node name', ids.node, detail, '冻结的读取页面'],
    ['uses the unnamed-node fallback', ids.operation, { ...detail, nodeNames: undefined }, '未命名节点'],
  ] as const)('%s while the selected node option is still loading', async (_case, selectedNode, taskDetail, label) => {
    render(<TaskDetail detail={taskDetail} attempts={undefined} logs={undefined} selectedTab="logs" selectedNode={selectedNode} level={null} query="" loading onTabChange={vi.fn()} onNodeChange={vi.fn()} onLevelChange={vi.fn()} onQueryChange={vi.fn()} onLoadMoreLogs={vi.fn()} onLoadMoreAttempts={vi.fn()} onLoadMoreOutputs={vi.fn()} onRetry={vi.fn()} onBack={vi.fn()} />)
    const select = screen.getByRole('combobox', { name: '筛选日志节点' })
    expect(select).toHaveTextContent(label)
    await userEvent.setup().click(select)
    expect(screen.getByRole('option', { name: label })).toBeVisible()
    expectNoInternalIdentity()
  })

  it('maps unknown structured and page errors without echoing internal diagnostics', () => {
    const evidence = render(<TaskEvidence mode="evidence" detail={detail} attempts={{ items: [attempt], page: 1, pageSize: 50, total: 1, sort: 'createdAt' }} error={`request ${ids.request}`} onLoadMoreAttempts={vi.fn()} onLoadMoreOutputs={vi.fn()} />)
    expect(screen.getByRole('heading', { name: '运行失败' })).toBeVisible()
    expect(screen.getByRole('alert')).toHaveTextContent('操作失败，请重试')
    expectNoInternalIdentity()
    evidence.unmount()
    render(<BatchDirectory error={`unknown ${ids.operation}`} filters={{ q: null, automationId: null, status: null, period: null }} onFiltersChange={vi.fn()} onPageChange={vi.fn()} onOpen={vi.fn()} onRetry={vi.fn()} />)
    expect(screen.getByRole('alert')).toHaveTextContent('操作失败，请重试')
    expectNoInternalIdentity()
  })

  it('forces the fixed phrase, starts on cancel, and cannot close while submitting', async () => {
    const user = userEvent.setup(), onOpenChange = vi.fn(), onConfirm = vi.fn()
    const view = render(<StopBatchDialog open force busy={false} automationName="参数运行验收" startedAt={batch.createdAt} activeTaskCount={2} error={undefined} onOpenChange={onOpenChange} onConfirm={onConfirm} />)
    expect(screen.getByRole('button', { name: '取消' })).toHaveFocus()
    expect(screen.getByText('参数运行验收')).toBeVisible(); expect(screen.getByText('2')).toBeVisible()
    expect(screen.getByRole('button', { name: '确认强制停止' })).toBeDisabled()
    await user.type(screen.getByRole('textbox', { name: '确认强制停止' }), '强制停止')
    await user.click(screen.getByRole('button', { name: '确认强制停止' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
    view.rerender(<StopBatchDialog open force busy automationName="参数运行验收" startedAt={batch.createdAt} activeTaskCount={2} error={undefined} onOpenChange={onOpenChange} onConfirm={onConfirm} />)
    await user.keyboard('{Escape}')
    expect(onOpenChange).not.toHaveBeenCalledWith(false)
    expectNoInternalIdentity()
  })
})
