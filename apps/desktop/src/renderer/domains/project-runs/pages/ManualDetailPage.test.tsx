import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { StreamingApiClient } from '../../../shared/api/client'
import { ManualDetailPage } from './ManualDetailPage'

const projectId = '00000000-0000-4000-8000-000000000001'
const manualItemId = '00000000-0000-4000-8000-00000000000d'
const taskId = '00000000-0000-4000-8000-00000000000e'
const runId = '00000000-0000-4000-8000-00000000000c'
const instanceId = '00000000-0000-4000-8000-00000000000a'

const item = {
  manualItemId,
  projectId,
  taskId,
  runId,
  instanceId,
  checkpointRevision: 3,
  status: 'waiting',
  statusRevision: 2,
  expiresAt: new Date(Date.now() + 13 * 60_000).toISOString(),
  allowedTargets: [] as unknown[],
  resumeStarted: false,
  reason: '需要核对提取的标题与日期',
  createdAt: '2026-09-18T05:00:00Z',
  updatedAt: '2026-09-18T05:00:00Z',
}

const instance = {
  instanceId, projectId, environmentId: null, state: 'waiting_manual', source: 'newFromProfile', sourceContentGeneration: null,
  instanceUseGeneration: 2, activeTaskId: taskId, activeRunId: runId, maintenanceOperationId: null, profileId: 'profile',
  createdAt: '2026-09-18T05:00:00Z', updatedAt: '2026-09-18T05:00:00Z',
}

const task = {
  automationName: '资料整理', batchStartedAt: null, parameterDefinitions: [],
  task: { taskId, projectId, batchId: runId, runId, runRequestId: runId, status: 'waiting_manual', statusRevision: 1, inputSnapshotId: 'snapshot', taskOrdinal: 13, automationName: '资料整理', batchStartedAt: null, inputIdentifier: 'R013', endNodeName: null, createdAt: '2026-09-18T05:00:00Z', completedAt: null },
  inputSnapshot: { inputSnapshotId: 'snapshot', taskId, batchId: runId, parameters: { 关键词: '温室' }, inputs: [], capturedAt: '2026-09-18T05:00:00Z' },
  run: { runId, runRequestId: runId, status: 'waiting_manual', statusRevision: 1, executionGeneration: 1, preparedContentId: 'content', capabilityBindings: [], resourceRequest: {}, lastSequence: 1 },
}

beforeEach(() => { vi.stubGlobal('crypto', { randomUUID: () => '00000000-0000-4000-8000-0000000000ff' }) })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

type Call = [string, { method?: string; body?: Record<string, unknown>; headers?: Record<string, string> } | undefined]

function renderPage(options: { item?: Record<string, unknown>; failFinish?: boolean; failResume?: boolean } = {}) {
  const manual = { ...item, ...options.item }
  const request = vi.fn(async (path: string, init?: { method?: string; body?: unknown }) => {
    if (path.endsWith('/open')) return { operation: { operationId: 'op-open', kind: 'openInstance', status: 'accepted' }, outcome: {} }
    if (path.endsWith('/resume')) {
      if (options.failResume) throw Object.assign(new Error('conflict'), { code: 'MANUAL_STATUS_CONFLICT' })
      return { operation: { operationId: 'op-resume', kind: 'resumeManual', status: 'succeeded' }, outcome: {} }
    }
    if (path.endsWith('/finish')) {
      if (options.failFinish) throw Object.assign(new Error('conflict'), { code: 'MANUAL_STATUS_CONFLICT' })
      return { operation: { operationId: 'op-finish', kind: 'finishManual', status: 'succeeded' }, outcome: {} }
    }
    if (path.includes(`/manual-items/${manualItemId}`)) return manual
    if (path.includes('/environment-instances/')) return instance
    if (path.includes(`/tasks/${taskId}`)) return task
    throw new Error(`unexpected ${path} ${init?.method ?? 'GET'}`)
  }) as unknown as StreamingApiClient['request']
  const client = { request, stream: vi.fn(), health: vi.fn() } as unknown as StreamingApiClient
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const onNavigate = vi.fn()
  render(<QueryClientProvider client={queryClient}><ManualDetailPage workspaceKey="workspace" instanceId="instance" projectId={projectId} client={client} disabled={false} readOnly={false} onNavigate={onNavigate} manualItemId={manualItemId}/></QueryClientProvider>)
  const calls = () => (request as unknown as { mock: { calls: Call[] } }).mock.calls
  const bodyOf = (suffix: string) => calls().find(([path]) => path.endsWith(suffix))?.[1]?.body
  return { request, onNavigate, calls, bodyOf }
}

const open = async () => {
  expect(await screen.findByRole('heading', { level: 1, name: /需要核对提取的标题与日期/ })).toBeVisible()
}

it('renders the frozen manual facts and keeps continue disabled when no target node exists', async () => {
  renderPage()
  await open()
  expect(screen.getByText('等待人工')).toBeVisible()
  expect(screen.getByText('剩余 13 分钟')).toBeVisible()
  expect(screen.getByText(/当前检查点没有管理页面可继续的目标节点/)).toBeVisible()
  expect(screen.getByRole('radio', { name: /继续工作流/ })).toBeDisabled()
  // 继续工作流不可用时不假装可提交，必须先显式选择处理方式
  expect(screen.getByRole('button', { name: '提交处理结果' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '返回等待人工' })).toBeVisible()
  // 环境实例尚未读回前不冒充可用，读回后按钮才启用
  await waitFor(() => expect(screen.getByRole('button', { name: '打开环境' })).toBeEnabled())
})

it('opens the live environment through the controlled instance command', async () => {
  const { bodyOf, calls } = renderPage()
  await open()
  const button = await screen.findByRole('button', { name: '打开环境' })
  await waitFor(() => expect(button).toBeEnabled())
  fireEvent.click(button)
  await waitFor(() => expect(calls().some(([path]) => path.endsWith(`/environment-instances/${instanceId}/open`))).toBe(true))
  expect(bodyOf(`/environment-instances/${instanceId}/open`)).toEqual({ expectedUseGeneration: 2 })
})

it('requires the acknowledgement inside the confirm dialog before completing', async () => {
  const { onNavigate, bodyOf } = renderPage()
  await open()
  fireEvent.click(screen.getByRole('radio', { name: /标记完成/ }))
  const submit = screen.getByRole('button', { name: '提交处理结果' })
  await waitFor(() => expect(submit).toBeEnabled())
  fireEvent.click(submit)
  expect(await screen.findByRole('heading', { name: '将这条任务标记完成？' })).toBeVisible()
  expect(screen.getByText('标记完成不等于资料已保存，也不会自动写入业务数据。')).toBeVisible()
  const confirm = screen.getByRole('button', { name: '确认标记完成' })
  expect(confirm).toBeDisabled()
  fireEvent.change(screen.getByLabelText('处理说明'), { target: { value: '已人工核对，后续由我维护资料。' } })
  fireEvent.click(screen.getByRole('checkbox', { name: '我已了解，本次处理不会继续工作流' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '确认标记完成' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: '确认标记完成' }))
  await waitFor(() => expect(bodyOf(`/manual-items/${manualItemId}/finish`)).toBeTruthy())
  expect(bodyOf(`/manual-items/${manualItemId}/finish`)).toMatchObject({
    outcome: 'succeeded',
    expectedCheckpointRevision: 3,
    expectedStatusRevision: 2,
    reason: '已人工核对，后续由我维护资料。',
    retainEnvironment: { enabled: false },
  })
  await waitFor(() => expect(onNavigate).toHaveBeenCalledWith({ projectId, tab: 'runs', runView: 'manual' }))
})

it('continues through the selected checkpoint target and sends the live revisions', async () => {
  const { onNavigate, bodyOf } = renderPage({ item: { allowedTargets: [{ nodeId: 'node-04', title: '保存资料' }] } })
  await open()
  fireEvent.click(screen.getByRole('radio', { name: /继续工作流/ }))
  // 目标节点选项只在选择「继续工作流」后出现，默认选中结构顺序中的第一项
  expect(await screen.findByText('保存资料')).toBeVisible()
  const submit = screen.getByRole('button', { name: '提交处理结果' })
  await waitFor(() => expect(submit).toBeEnabled())
  fireEvent.click(submit)
  await waitFor(() => expect(bodyOf(`/manual-items/${manualItemId}/resume`)).toBeTruthy())
  expect(bodyOf(`/manual-items/${manualItemId}/resume`)).toMatchObject({ checkpointRevision: 3, expectedStatusRevision: 2, targetNodeId: 'node-04' })
  await waitFor(() => expect(onNavigate).toHaveBeenCalledWith({ projectId, tab: 'runs', runView: 'manual' }))
})

it('keeps a failed submission on the page, preserves the typed reason and requires a reason for failure', async () => {
  const { onNavigate, bodyOf, calls } = renderPage({ failFinish: true })
  await open()
  fireEvent.click(screen.getByRole('radio', { name: /标记失败/ }))
  const submit = screen.getByRole('button', { name: '提交处理结果' })
  // 失败必须填写说明，空说明不能提交
  expect(submit).toBeDisabled()
  fireEvent.change(screen.getByLabelText('失败说明'), { target: { value: '页面缺少必需列，无法继续' } })
  await waitFor(() => expect(submit).toBeEnabled())
  fireEvent.click(submit)
  await waitFor(() => expect(calls().some(([path]) => path.endsWith(`/manual-items/${manualItemId}/finish`))).toBe(true))
  expect(bodyOf(`/manual-items/${manualItemId}/finish`)).toMatchObject({ outcome: 'failed', reason: '页面缺少必需列，无法继续', expectedCheckpointRevision: 3, expectedStatusRevision: 2 })
  // 失败留在页面：显示错误、保留原输入、不清空身份也不跳转
  expect(await screen.findByRole('alert')).toHaveTextContent('提交处理结果失败')
  expect(screen.getByLabelText('失败说明')).toHaveValue('页面缺少必需列，无法继续')
  expect(screen.getByRole('heading', { level: 1, name: /需要核对提取的标题与日期/ })).toBeVisible()
  expect(onNavigate).not.toHaveBeenCalled()
  // 允许用同一事项的现场版本重试，而不是伪造成功
  await waitFor(() => expect(screen.getByRole('button', { name: '提交处理结果' })).toBeEnabled())
  expect(bodyOf(`/manual-items/${manualItemId}/finish`)).toMatchObject({ expectedStatusRevision: 2 })
})

it('replaces the unusable form with confirmed facts once the item is no longer waiting', async () => {
  const { onNavigate } = renderPage({ item: { status: 'expired', expiresAt: new Date(Date.now() - 60_000).toISOString() } })
  await open()
  expect(await screen.findByRole('heading', { name: '处理结果' })).toBeVisible()
  expect(screen.getByText('保留时间已到，不能再提交人工处理。')).toBeVisible()
  expect(screen.getByRole('region', { name: '处理结果' })).toBeVisible()
  expect(screen.getByRole('region', { name: '历史现场' })).toBeVisible()
  expect(screen.getByText('历史证据可查看；现场不再用于继续执行。')).toBeVisible()
  expect(screen.getByText('管理侧只登记已确认的事实，不根据倒计时推断环境与占用的清理结果。')).toBeVisible()
  // 任务状态用产品语言，不把服务端内部值直接当主要内容
  expect(screen.getByText('任务状态').parentElement).toHaveTextContent('等待人工')
  expect(screen.queryByText(/waiting_manual/)).not.toBeInTheDocument()
  // 终态不再渲染不可用的提交表单，也不冒充已确认的清理结果
  expect(screen.queryByRole('button', { name: '提交处理结果' })).not.toBeInTheDocument()
  expect(screen.queryByRole('region', { name: '处理方式' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '打开环境' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '查看任务日志' }))
  expect(onNavigate).toHaveBeenCalledWith({ projectId, tab: 'runs', taskId, taskTab: 'logs' })
})
