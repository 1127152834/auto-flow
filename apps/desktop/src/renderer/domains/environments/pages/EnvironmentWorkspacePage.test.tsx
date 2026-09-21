import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { StreamingApiClient } from '../../../shared/api/client'
import type { ProjectView } from '../../projects/types'
import { EnvironmentWorkspacePage } from './EnvironmentWorkspacePage'

const projectId = '00000000-0000-4000-8000-000000000001'
const project = {
  defaultResources: { profileId: null, proxy: { mode: 'sourceDefault' }, modelProviderId: null },
} as unknown as ProjectView

const instance = {
  instanceId: '00000000-0000-4000-8000-00000000000a',
  projectId,
  environmentId: null,
  state: 'active',
  source: 'newFromProfile',
  sourceContentGeneration: null,
  instanceUseGeneration: 1,
  activeTaskId: '00000000-0000-4000-8000-00000000000b',
  activeRunId: '00000000-0000-4000-8000-00000000000c',
  maintenanceOperationId: null,
  profileId: 'profile',
  createdAt: '2026-09-18T00:00:00Z',
  updatedAt: '2026-09-18T00:00:00Z',
}

const manualItem = {
  manualItemId: '00000000-0000-4000-8000-00000000000d',
  projectId,
  taskId: '00000000-0000-4000-8000-00000000000e',
  runId: '00000000-0000-4000-8000-00000000000c',
  instanceId: instance.instanceId,
  checkpointRevision: 1,
  status: 'waiting',
  statusRevision: 1,
  expiresAt: new Date(Date.now() + 13 * 60_000).toISOString(),
  allowedTargets: [],
  resumeStarted: false,
  reason: '需要人工完成验证码',
  createdAt: '2026-09-18T00:00:00Z',
  updatedAt: '2026-09-18T00:00:00Z',
}

beforeEach(() => {
  vi.stubGlobal('crypto', { randomUUID: () => '00000000-0000-4000-8000-0000000000ff' })
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const automaticInstance = {
  ...instance,
  instanceId: '00000000-0000-4000-8000-000000000010',
  activeTaskId: '00000000-0000-4000-8000-000000000011',
  activeRunId: '00000000-0000-4000-8000-000000000012',
}

function renderPage(instances: unknown[] = [instance]) {
  const request = vi.fn(async (path: string) => {
    if (path.includes('/environment-instances?')) return { items: instances, page: 1, pageSize: 50, total: instances.length, sort: '-updatedAt' }
    if (path.includes('/manual-items')) return { items: [manualItem], page: 1, pageSize: 50, total: 1 }
    if (path.includes('/environments?')) return { items: [], page: 1, pageSize: 50, total: 0, sort: '-updatedAt' }
    throw new Error(`unexpected ${path}`)
  }) as unknown as StreamingApiClient['request']
  const client = { request, stream: vi.fn(), health: vi.fn() } as unknown as StreamingApiClient
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const onNavigate = vi.fn()
  render(<QueryClientProvider client={queryClient}><EnvironmentWorkspacePage
    workspaceKey="workspace"
    instanceId="instance"
    projectId={projectId}
    project={project}
    client={client}
    disabled={false}
    readOnly={false}
    onNavigate={onNavigate}
  /></QueryClientProvider>)
  return { onNavigate }
}

it('opens on the current scene, keeps the two overview shortcuts, and lists live work', async () => {
  const { onNavigate } = renderPage()
  // 原型 001 的默认分区是"运行环境"，主列标题是"当前现场"
  expect(await screen.findByRole('heading', { name: '当前现场', level: 2 })).toBeVisible()
  await waitFor(() => expect(screen.getByText('1 个临时现场 · 含 1 个等待人工')).toBeVisible())
  expect(screen.getByRole('region', { name: '项目默认资源概览' })).toBeVisible()
  expect(screen.getByRole('region', { name: '持久环境概览' })).toBeVisible()
  expect(screen.getByRole('button', { name: '查看持久环境 0' })).toBeVisible()
  expect(screen.getByRole('heading', { name: '需要人工处理 1', level: 3 })).toBeVisible()
  expect(screen.getByText('需要人工完成验证码')).toBeVisible()
  expect(screen.getByText('剩余 13 分钟')).toBeVisible()
  const enter = screen.getByRole('button', { name: '进入人工处理' })
  expect(enter).toBeEnabled()
  // 人工处理在运行记录里只有一份详情，环境页不再自己开一份浏览器
  enter.click()
  expect(onNavigate).toHaveBeenCalledWith({ projectId, tab: 'runs', runView: 'manual', manualItemId: manualItem.manualItemId })
  screen.getByRole('button', { name: '继续原任务' }).click()
  expect(onNavigate).toHaveBeenLastCalledWith({ projectId, tab: 'runs', runView: 'manual', manualItemId: manualItem.manualItemId })
  screen.getByRole('button', { name: '明确结束' }).click()
  expect(onNavigate).toHaveBeenLastCalledWith({ projectId, tab: 'runs', runView: 'manual', manualItemId: manualItem.manualItemId })
  // 任务与批次入口是可点击的真实跳转，不是编造的编号
  screen.getAllByRole('button', { name: '查看任务' })[0].click()
  expect(onNavigate).toHaveBeenCalledWith({ projectId, tab: 'runs', runView: 'tasks', taskId: manualItem.taskId, taskTab: 'logs' })
  // 等待人工的现场不再被重复列进"自动运行"，只有真正自动运行的副本进入该小节
  expect(screen.queryByRole('heading', { name: /自动运行/ })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '查看批次' })).not.toBeInTheDocument()
  cleanup()
  const automatic = renderPage([instance, automaticInstance])
  expect(await screen.findByRole('heading', { name: '自动运行 1', level: 3 })).toBeVisible()
  expect(await screen.findByText('2 个临时现场 · 含 1 个等待人工')).toBeVisible()
  screen.getByRole('button', { name: '查看批次' }).click()
  expect(automatic.onNavigate).toHaveBeenCalledWith({ projectId, tab: 'runs', runView: 'batches', batchId: automaticInstance.activeRunId })
})

it('switches the empty current scene to a plain statement instead of a zero count', async () => {
  const request = vi.fn(async (path: string) => {
    if (path.includes('/environment-instances?')) return { items: [], page: 1, pageSize: 50, total: 0, sort: '-updatedAt' }
    if (path.includes('/manual-items')) return { items: [], page: 1, pageSize: 50, total: 0 }
    if (path.includes('/environments?')) return { items: [], page: 1, pageSize: 50, total: 0, sort: '-updatedAt' }
    throw new Error(`unexpected ${path}`)
  }) as unknown as StreamingApiClient['request']
  const client = { request, stream: vi.fn(), health: vi.fn() } as unknown as StreamingApiClient
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={queryClient}><EnvironmentWorkspacePage workspaceKey="workspace" instanceId="instance" projectId={projectId} project={project} client={client} disabled={false} readOnly={false} onNavigate={vi.fn()} /></QueryClientProvider>)
  expect(await screen.findByText('当前没有临时现场')).toBeVisible()
  expect(screen.queryByRole('heading', { name: /需要人工处理/ })).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: /自动运行/ })).not.toBeInTheDocument()
})
