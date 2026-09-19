import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { StreamingApiClient } from '../../../shared/api/client'
import { choiceTestEnvironment, chooseOption } from '../../../shared/testing/choice-user'
import { TaskDetailPage } from './TaskDetailPage'

afterEach(() => { cleanup(); vi.restoreAllMocks() })
choiceTestEnvironment()
const detail = { automationName: '链接采集', parameterDefinitions: [], nodeNames: { 'node-1': '节点一', 'node-2': '节点二', 'node-submit': '点击提交' }, task: { taskId: 'task-1', projectId: 'project-1', batchId: 'batch-1', runId: 'run-1', runRequestId: 'request-1', status: 'succeeded', statusRevision: 2, inputSnapshotId: 'snapshot-1', taskOrdinal: 1, createdAt: '2026-09-15T01:00:00Z', completedAt: '2026-09-15T01:01:00Z' }, inputSnapshot: { inputSnapshotId: 'snapshot-1', taskId: 'task-1', batchId: 'batch-1', parameters: {}, inputs: [], capturedAt: '2026-09-15T01:00:00Z' }, run: { runId: 'run-1', runRequestId: 'request-1', status: 'succeeded', statusRevision: 2, executionGeneration: 1, preparedContentId: 'content-1', capabilityBindings: [], resourceRequest: {}, lastSequence: 2, terminal: true, startedAt: '2026-09-15T01:00:00Z', finishedAt: '2026-09-15T01:01:00Z' }, cleanup: { status: 'notRequired' as const, operationId: null, message: null } }
const attempt = (id: string, nodeId: string, nodeName: string) => ({ nodeVisitId: id, nodeId, nodeName, attempt: 1, status: 'succeeded', startedAt: '2026-09-15T01:00:00Z', completedAt: '2026-09-15T01:00:01Z', error: null })
const log = (sequence: number, message: string) => ({ runId: 'run-1', sequence, eventId: `event-${sequence}`, executionGeneration: 1, level: 'info', message, occurredAt: '2026-09-15T01:00:00Z' })

function renderPage(request: StreamingApiClient['request'], overrides: Partial<React.ComponentProps<typeof TaskDetailPage>> = {}, stream = vi.fn()) {
  const wrapped: StreamingApiClient['request'] = async (path, init) => {
    if (String(path).includes('/environment-instances')) return { items: [], page: 1, pageSize: 5, total: 0, sort: '-updatedAt' } as never
    return request(path, init)
  }
  const client = { request: wrapped, stream } as unknown as StreamingApiClient
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const props = { workspaceKey: 'workspace-1', instanceId: 'instance-1', projectId: 'project-1', taskId: 'task-1', tab: 'logs' as const, client, disabled: false, readOnly: false, onNavigate: vi.fn(), ...overrides }
  return { ...render(<QueryClientProvider client={queryClient}><TaskDetailPage {...props}/></QueryClientProvider>), props, queryClient, client }
}

it('loads additional terminal attempt and log pages only when the user asks', async () => {
  const request = vi.fn(async (path: string) => {
    if (path.endsWith('/tasks/task-1')) return detail
    if (path.includes('node-attempts?page=1')) return { items: [attempt('visit-1', 'node-1', '节点一')], page: 1, pageSize: 1, total: 2, sort: 'createdAt' }
    if (path.includes('node-attempts?page=2')) return { items: [attempt('visit-2', 'node-2', '节点二')], page: 2, pageSize: 1, total: 2, sort: 'createdAt' }
    if (path.includes('logs?afterSequence=0')) return { items: [log(1, '第一段日志')], afterSequence: 1, lastSequence: 80, hasMore: true }
    if (path.includes('logs?afterSequence=1')) return { items: [log(2, '第二段日志')], afterSequence: 2, lastSequence: 80, hasMore: false }
    throw new Error(`unexpected ${path}`)
  })
  renderPage(request as StreamingApiClient['request'])
  expect(await screen.findByText('第一段日志')).toBeVisible()
  expect(screen.getByRole('button', { name: /节点一/ })).toBeVisible()
  expect(screen.queryByText('第二段日志')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /节点二/ })).not.toBeInTheDocument()
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: '加载更多尝试' }))
  await user.click(screen.getByRole('button', { name: '加载更多日志' }))
  expect(await screen.findByText('第二段日志')).toBeVisible()
  expect(screen.getByRole('button', { name: /节点二/ })).toBeVisible()
  expect(request).toHaveBeenCalledWith(expect.stringContaining('logs?afterSequence=1'), expect.anything())
})

it('isolates filtered log reads and routes tabs and batch return', async () => {
  const request = vi.fn(async (path: string) => {
    if (path.endsWith('/tasks/task-1')) return detail
    if (path.includes('node-attempts')) return { items: [], page: 1, pageSize: 100, total: 0, sort: 'createdAt' }
    if (path.includes('logs?')) return { items: [log(1, path.includes('level=error') ? '仅错误' : '全部日志')], afterSequence: 0, lastSequence: 1, hasMore: false }
    if (path.includes('outputs')) return { items: [], page: 1, pageSize: 100, total: 0, sort: 'createdAt' }
    throw new Error(`unexpected ${path}`)
  }) as StreamingApiClient['request']
  const { props } = renderPage(request)
  await screen.findByText('全部日志')
  const user = userEvent.setup()
  await chooseOption(user, screen.getByRole('combobox', { name: '筛选日志级别' }), 'error')
  expect(await screen.findByText('仅错误')).toBeVisible()
  expect(request).toHaveBeenCalledWith(expect.stringContaining('level=error'), expect.anything())
  await user.click(screen.getByRole('tab', { name: '输入与输出' }))
  expect(props.onNavigate).toHaveBeenCalledWith({ projectId: 'project-1', tab: 'runs', taskId: 'task-1', taskTab: 'io' })
  await user.click(screen.getByRole('button', { name: /返回批次/ }))
  expect(props.onNavigate).toHaveBeenCalledWith({ projectId: 'project-1', tab: 'runs', runView: 'batches', batchId: 'batch-1' })
})

it('does not request while typing and applies or clears the explicit log query', async () => {
  const request = vi.fn(async (path: string) => {
    if (path.endsWith('/tasks/task-1')) return detail
    if (path.includes('node-attempts')) return { items: [], page: 1, pageSize: 100, total: 0, sort: 'createdAt' }
    if (path.includes('logs?')) return { items: [log(1, path.includes('query=%E8%B6%85%E6%97%B6') ? '搜索结果' : '全部日志')], afterSequence: 1, lastSequence: 1, hasMore: false }
    throw new Error(`unexpected ${path}`)
  })
  renderPage(request as StreamingApiClient['request'])
  await screen.findByText('全部日志')
  const user = userEvent.setup()
  const search = screen.getByRole('searchbox', { name: '搜索日志内容' })
  const readsBeforeTyping = request.mock.calls.filter(([path]) => String(path).includes('/logs?')).length
  await user.type(search, '超时')
  expect(request.mock.calls.filter(([path]) => String(path).includes('/logs?'))).toHaveLength(readsBeforeTyping)
  await user.click(screen.getByRole('button', { name: '应用日志搜索' }))
  expect(await screen.findByText('搜索结果')).toBeVisible()
  expect(request).toHaveBeenCalledWith(expect.stringContaining('query=%E8%B6%85%E6%97%B6'), expect.anything())
  await user.click(screen.getByRole('button', { name: '清除日志搜索' }))
  expect(await screen.findByText('全部日志')).toBeVisible()
  expect(screen.queryByText('没有匹配的日志。')).not.toBeInTheDocument()
})

it('keeps stale facts visible on refresh failure and exposes initial failure recovery', async () => {
  let detailReads = 0
  const request = vi.fn(async (path: string) => {
    if (path.endsWith('/tasks/task-1')) { detailReads++; if (detailReads > 1) throw new Error('刷新失败'); return detail }
    if (path.includes('node-attempts')) return { items: [], page: 1, pageSize: 100, total: 0, sort: 'createdAt' }
    if (path.includes('logs?')) return { items: [log(1, '已保存事实')], afterSequence: 0, lastSequence: 1, hasMore: false }
    throw new Error(`unexpected ${path}`)
  }) as StreamingApiClient['request']
  const { props, queryClient, unmount } = renderPage(request)
  await screen.findByText('已保存事实')
  await queryClient.invalidateQueries({ queryKey: ['workspace-1', 'instance-1', 'project-runs', 'project-1', 'task', 'task-1', 'detail'] })
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('刷新失败'))
  expect(screen.getByText('已保存事实')).toBeVisible()
  unmount()
  const failed = vi.fn().mockRejectedValue(new Error('任务不存在')) as StreamingApiClient['request']
  const second = renderPage(failed)
  expect(await screen.findByRole('alert')).toHaveTextContent('无法读取任务：操作失败，请重试')
  await userEvent.click(screen.getByRole('button', { name: '返回任务目录' }))
  expect(second.props.onNavigate).toHaveBeenCalledWith({ projectId: 'project-1', tab: 'runs', runView: 'tasks' })
  expect(props.onNavigate).not.toHaveBeenCalledWith(expect.objectContaining({ runView: 'tasks' }))
})

it('subscribes active tasks and aborts the scoped stream when the page unmounts', async () => {
  const active = { ...detail, task: { ...detail.task, status: 'running', completedAt: null }, run: { ...detail.run, status: 'running', terminal: false, finishedAt: null } }
  const request = vi.fn(async (path: string) => {
    if (path.endsWith('/tasks/task-1')) return active
    if (path.endsWith('/events?afterSequence=0')) return { items: [], afterSequence: 0, lastSequence: 0, hasMore: false, terminal: false }
    if (path.includes('node-attempts')) return { items: [], page: 1, pageSize: 100, total: 0, sort: 'createdAt' }
    if (path.includes('logs?')) return { items: [], afterSequence: 0, lastSequence: 0, hasMore: false }
    throw new Error(`unexpected ${path}`)
  }) as StreamingApiClient['request']
  let streamSignal: AbortSignal | undefined
  const stream = vi.fn(async (_path: string, init?: RequestInit) => {
    streamSignal = init?.signal ?? undefined
    return new Response(new ReadableStream({ start() { /* stays open until unmount */ } }), { headers: { 'content-type': 'text/event-stream' } })
  })
  const view = renderPage(request, {}, stream)
  await waitFor(() => expect(stream).toHaveBeenCalledOnce())
  expect(streamSignal?.aborted).toBe(false)
  view.unmount()
  expect(streamSignal?.aborted).toBe(true)
})

it('loads authenticated failure evidence and opens the screenshot preview', async () => {
  const artifact = { artifactId: 'artifact-1', kind: 'screenshot', purpose: 'error', availability: 'available', nodeId: 'node-submit', nodeName: '点击提交', nodeVisitId: 'visit-1', eventSequence: 9, executionGeneration: 1, mediaType: 'image/png', byteSize: 3, sha256: 'hash', createdAt: '2026-09-15T01:00:02Z', contentUrl: '/content' }
  const request = vi.fn(async (path: string) => {
    if (path.endsWith('/tasks/task-1')) return { ...detail, task: { ...detail.task, status: 'failed' }, run: { ...detail.run, status: 'failed', error: { code: 'NODE_FAILED' } } }
    if (path.includes('node-attempts')) return { items: [], page: 1, pageSize: 100, total: 0, sort: 'createdAt' }
    if (path.includes('/outputs')) return { items: [], page: 1, pageSize: 100, total: 0, sort: 'createdAt' }
    if (path.includes('/artifacts?')) return { items: [artifact], page: 1, pageSize: 100, total: 1, sort: 'createdAt' }
    throw new Error(`unexpected ${path}`)
  }) as StreamingApiClient['request']
  const createObjectURL = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:failure')
  const revokeObjectURL = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
  const stream = vi.fn().mockResolvedValue(new Response(new Uint8Array([1, 2, 3]), { headers: { 'content-type': 'image/png' } }))
  const view = renderPage(request, { tab: 'evidence' }, stream)

  await userEvent.click(await screen.findByRole('button', { name: '查看失败截图：点击提交' }))
  expect(await screen.findByRole('img', { name: '失败截图：点击提交' })).toHaveAttribute('src', 'blob:failure')
  expect(stream).toHaveBeenCalledWith(expect.stringContaining('/artifacts/artifact-1/content'), expect.objectContaining({ signal: expect.any(AbortSignal) }))
  expect(createObjectURL).toHaveBeenCalledOnce()
  view.unmount()
  expect(revokeObjectURL).toHaveBeenCalledWith('blob:failure')
})
