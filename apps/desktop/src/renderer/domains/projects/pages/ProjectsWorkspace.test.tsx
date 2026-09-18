import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import userEvent from '@testing-library/user-event'
import { ApiClientError, type StreamingApiClient } from '../../../shared/api/client'
import type { ProjectSummary, ProjectView } from '../types'
import { ProjectsWorkspace, resetProjectUiState } from './ProjectsWorkspace'

const base = { description: '', managementRevision: 1, lifecycleState: 'active', defaultResources: { profileId: null, proxy: { mode: 'none' }, modelProviderId: null }, createdAt: '2026-09-13T00:00:00Z', updatedAt: '2026-09-13T00:00:00Z', lastOpenedAt: null, availability: { automations: 'notImplemented', data: 'available', runs: 'notImplemented', environments: 'available', statistics: 'notImplemented', sync: 'notImplemented' } }
const a = { ...base, projectId: '00000000-0000-4000-8000-000000000001', name: '项目A' } as ProjectSummary
const b = { ...base, projectId: '00000000-0000-4000-8000-000000000002', name: '项目B' } as ProjectSummary
class ResizeObserverStub { observe() {}; unobserve() {}; disconnect() {} }
beforeEach(() => { vi.stubGlobal('ResizeObserver', ResizeObserverStub); sessionStorage.clear(); sessionStorage.setItem('autoflow:projects-ui:w1', JSON.stringify({mode:'all'})) })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

function deferred<T>() { let resolve!: (value: T) => void; let reject!: (reason: unknown) => void; return { promise: new Promise<T>((yes, no) => { resolve = yes; reject = no }), resolve, reject } }
function mount(request: StreamingApiClient['request'], props: Partial<Parameters<typeof ProjectsWorkspace>[0]> = {}) {
  const onNavigate = vi.fn(); const client = { request, health: vi.fn(), stream: vi.fn() } as StreamingApiClient
  const values = { route: { tab: 'overview' as const }, workspaceKey: 'w1', instanceId: 'i1', client, disabled: false, onNavigate, registerLeaveGuard: vi.fn(), ...props }
  const view = render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ProjectsWorkspace {...values} /></QueryClientProvider>)
  return { ...view, onNavigate, values }
}

it('only lets the latest same-instance open request navigate', async () => {
  const opens = new Map([[a.projectId, deferred<{ project: ProjectView }>()], [b.projectId, deferred<{ project: ProjectView }>()]])
  const request = vi.fn((path: string) => path.includes('/open') ? opens.get(path.split('/').at(-2)!)!.promise : Promise.resolve({ items: [a, b], page: 1, pageSize: 50, total: 2, sort: '-lastOpenedAt' }))
  const { onNavigate } = mount(request as unknown as StreamingApiClient['request'])
  fireEvent.click(await screen.findByRole('button', { name: '项目A' })); fireEvent.click(screen.getByRole('button', { name: '项目B' }))
  opens.get(b.projectId)!.resolve({ project: b as ProjectView }); await waitFor(() => expect(onNavigate).toHaveBeenCalledWith({ projectId: b.projectId, tab: 'overview' }))
  opens.get(a.projectId)!.resolve({ project: a as ProjectView }); await Promise.resolve()
  expect(onNavigate).toHaveBeenCalledTimes(1)
})

it('ignores an open error from a replaced instance', async () => {
  const opening = deferred<{ project: ProjectView }>()
  const request = vi.fn((path: string) => path.includes('/open') ? opening.promise : Promise.resolve({ items: [a], page: 1, pageSize: 50, total: 1, sort: '-lastOpenedAt' }))
  const mounted = mount(request as unknown as StreamingApiClient['request'])
  fireEvent.click(await screen.findByRole('button', { name: '项目A' }))
  mounted.rerender(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ProjectsWorkspace {...mounted.values} instanceId="i2" /></QueryClientProvider>)
  opening.reject(new Error('旧连接失败')); await Promise.resolve(); await Promise.resolve()
  expect(screen.queryByText('旧连接失败')).not.toBeInTheDocument()
})

it('restores directory conditions from the workspace session and reset clears them', async () => {
  sessionStorage.setItem('autoflow:projects-ui:w1', JSON.stringify({ mode: 'all', query: '保留搜索', lifecycle: 'archived', sort: 'name', page: 3, pageSize: 50, scrollTop: 80 }))
  const request = vi.fn().mockResolvedValue({ items: [], page: 3, pageSize: 50, total: 0, sort: 'name' })
  mount(request)
  expect(await screen.findByLabelText('搜索项目')).toHaveValue('保留搜索')
  await waitFor(() => expect(request.mock.calls[0]?.[0]).toContain('page=3'))
  resetProjectUiState('w1'); expect(sessionStorage.getItem('autoflow:projects-ui:w1')).toBeNull()
})

it('stores and restores the directory viewport scroll position', async () => {
  const request = vi.fn().mockResolvedValue({ items: [a], page: 1, pageSize: 50, total: 1, sort: '-lastOpenedAt' })
  const first = mount(request)
  await screen.findByText('项目A')
  const viewport = first.container.querySelector<HTMLElement>('.af-scroll-area > div')!
  Object.defineProperty(viewport, 'scrollTop', { value: 96, writable: true })
  fireEvent.scroll(viewport)
  expect(JSON.parse(sessionStorage.getItem('autoflow:projects-ui:w1')!).scrollPositions.all).toBe(96)
  first.unmount()
  const second = mount(request)
  await screen.findByText('项目A')
  expect(second.container.querySelector<HTMLElement>('.af-scroll-area > div')!.scrollTop).toBe(96)
})

it('locks changes during an unknown create and reconciles its retained key without a duplicate POST', async () => {
  vi.stubGlobal('crypto', { randomUUID: () => '00000000-0000-4000-8000-000000000099' })
  const calls: Array<{ path: string; method?: string; body?: unknown }> = []
  let workspaceLookups = 0
  const request = vi.fn((path: string, init?: { method?: string; body?: unknown }) => {
    calls.push({ path, method: init?.method, body: init?.body })
    if (path.includes('/workspace/operations/')) {
      workspaceLookups += 1
      if (workspaceLookups === 1) return Promise.reject(new TypeError('连接中断'))
      return Promise.resolve({ status: 'succeeded', kind: 'createProject', resource: { type: 'project', projectId: a.projectId }, result: { ...a, name: '原始草稿' } })
    }
    if (init?.method === 'POST') return Promise.reject(new TypeError('连接中断'))
    return Promise.resolve({ items: [], page: 1, pageSize: 50, total: 0, sort: '-lastOpenedAt' })
  })
  mount(request as StreamingApiClient['request'])
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: '新建项目' }))
  await user.type(screen.getByLabelText('项目名称'), '原始草稿')
  await user.click(screen.getByRole('button', { name: '创建项目' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('保存结果尚未确认')
  expect(screen.getByLabelText('项目名称')).toHaveAttribute('readonly')
  await user.type(screen.getByLabelText('项目名称'), '已改变')
  expect(screen.getByLabelText('项目名称')).toHaveValue('原始草稿')
  await user.click(screen.getByRole('button', { name: '核对保存结果' }))
  await waitFor(() => expect(calls.filter(call => call.path.includes('/workspace/operations/'))).toHaveLength(2))
  expect(calls.filter(call => call.method === 'POST')).toHaveLength(1)
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(calls[0]?.body).not.toMatchObject({ defaultResources: expect.anything() })
})

it('clears the synchronous leave guard before navigating after a successful create', async () => {
  let guard: (() => Promise<boolean>) | null = null
  const navigated = vi.fn()
  const created = { ...a, name: '新项目' } as ProjectView
  const request = vi.fn((path: string, init?: { method?: string }) => init?.method === 'POST' ? Promise.resolve(created) : Promise.resolve({ items: [], page: 1, pageSize: 50, total: 0, sort: '-lastOpenedAt' }))
  mount(request as unknown as StreamingApiClient['request'], {
    registerLeaveGuard: value => { guard = value },
    onNavigate: route => { void guard?.().then(allowed => { if (allowed) navigated(route) }) },
  })
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: '新建项目' }))
  await user.type(screen.getByLabelText('项目名称'), '新项目')
  await user.click(screen.getByRole('button', { name: '创建项目' }))
  await waitFor(() => expect(navigated).toHaveBeenCalledWith({ projectId: a.projectId, tab: 'overview' }))
})

it('does not close or navigate the current editor for a late create success from an old instance', async () => {
  const create = deferred<ProjectView>()
  const request = vi.fn((_path: string, init?: { method?: string }) => init?.method === 'POST' ? create.promise : Promise.resolve({ items: [], page: 1, pageSize: 50, total: 0, sort: '-lastOpenedAt' }))
  const mounted = mount(request as unknown as StreamingApiClient['request'])
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: '新建项目' }))
  await user.type(screen.getByLabelText('项目名称'), '旧实例项目')
  await user.click(screen.getByRole('button', { name: '创建项目' }))
  mounted.rerender(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ProjectsWorkspace {...mounted.values} instanceId="i2" /></QueryClientProvider>)
  create.resolve({ ...a, name: '旧实例项目' } as ProjectView)
  await Promise.resolve(); await Promise.resolve()
  expect(mounted.onNavigate).not.toHaveBeenCalled()
  expect(screen.getByLabelText('项目名称')).toHaveValue('旧实例项目')
})

it('uses a new command after a definitive name conflict rather than replaying the rejected body', async () => {
  const bodies: Array<{ name: string }> = []
  const request = vi.fn((path: string, init?: { method?: string; body?: { name: string } }) => {
    if (init?.method === 'POST') {
      bodies.push(init.body!)
      return bodies.length === 1 ? Promise.reject(new ApiClientError('名称已使用', 409, 'PROJECT_NAME_CONFLICT', { fields: { name: '名称已使用' } })) : Promise.resolve({ ...a, name: init.body!.name })
    }
    if (path.includes('/operations/')) throw new Error('Definitive rejection must not be reconciled')
    return Promise.resolve({ items: [], page: 1, pageSize: 50, total: 0, sort: '-lastOpenedAt' })
  })
  const mounted = mount(request as StreamingApiClient['request'])
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: '新建项目' }))
  await user.type(screen.getByLabelText('项目名称'), '冲突名称')
  await user.click(screen.getByRole('button', { name: '创建项目' }))
  await screen.findByText('项目名称已存在，请使用其他名称')
  await user.clear(screen.getByLabelText('项目名称')); await user.type(screen.getByLabelText('项目名称'), '更正名称')
  await user.click(screen.getByRole('button', { name: '创建项目' }))
  await waitFor(() => expect(mounted.onNavigate).toHaveBeenCalled())
  expect(bodies.map(body => body.name)).toEqual(['冲突名称', '更正名称'])
})

it('revokes a late open response after the project module is unmounted', async () => {
  const opening = deferred<{ project: ProjectView }>()
  const request = vi.fn((path: string) => path.endsWith('/open') ? opening.promise : Promise.resolve({ items: [a], page: 1, pageSize: 50, total: 1, sort: '-lastOpenedAt' }))
  const mounted = mount(request as StreamingApiClient['request'])
  fireEvent.click(await screen.findByRole('button', { name: '项目A' }))
  mounted.unmount(); opening.resolve({ project: a })
  await new Promise(resolve => setTimeout(resolve, 0))
  expect(mounted.onNavigate).not.toHaveBeenCalled()
})

it('corrects a restored page when the current result set has shrunk', async () => {
  sessionStorage.setItem('autoflow:projects-ui:w1', JSON.stringify({ mode: 'all', page: 3 }))
  const request = vi.fn(async (path: string) => ({ items: [], page: Number(new URL(path, 'http://local').searchParams.get('page')), pageSize: 50, total: 0, sort: '-lastOpenedAt' }))
  mount(request as StreamingApiClient['request'])
  await waitFor(() => expect(request.mock.calls.some(([path]) => path.includes('page=1&'))).toBe(true))
})

it('shows overview failure with retry while retaining real project details', async () => {
  const request = vi.fn((path: string) => path.endsWith('/overview') ? Promise.reject(new Error('概览连接失败')) : Promise.resolve(path.includes('?') ? { items: [a], page: 1, pageSize: 50, total: 1, sort: '-lastOpenedAt' } : a))
  mount(request as StreamingApiClient['request'], { route: { projectId: a.projectId, tab: 'overview' } })
  expect(await screen.findByRole('alert')).toHaveTextContent('操作失败，请重试')
  expect(screen.getByRole('button', { name: '重试概览' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: '项目资料' })).toBeInTheDocument()
})

it('refetches the overview every time the user comes back to the overview tab', async () => {
  const overviewCalls: string[] = []
  const project = { ...a } as ProjectView
  const request = vi.fn((path: string) => {
    if (path.endsWith('/overview')) { overviewCalls.push(path); return Promise.resolve({ project, availability: project.availability, counts: { tables: overviewCalls.length }, activity: [], current: [], recent: [] }) }
    return Promise.resolve(path.includes('?') ? { items: [], page: 1, pageSize: 50, total: 0, sort: '-lastOpenedAt' } : project)
  })
  const onNavigate = vi.fn(); const client = { request: request as unknown as StreamingApiClient['request'], health: vi.fn(), stream: vi.fn() } as StreamingApiClient
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const tree = (route: Parameters<typeof ProjectsWorkspace>[0]['route']) => <QueryClientProvider client={cache}><ProjectsWorkspace route={route} workspaceKey="w1" instanceId="i1" client={client} disabled={false} onNavigate={onNavigate} registerLeaveGuard={vi.fn()} /></QueryClientProvider>
  const view = render(tree({ projectId: a.projectId, tab: 'overview' }))
  await waitFor(() => expect(overviewCalls).toHaveLength(1))
  view.rerender(tree({ projectId: a.projectId, tab: 'runs' }))
  await waitFor(() => expect(document.querySelector('[aria-label="项目计数"]')).toBeNull())
  view.rerender(tree({ projectId: a.projectId, tab: 'overview' }))
  await waitFor(() => expect(overviewCalls).toHaveLength(2))
  expect(await screen.findByText('2')).toBeInTheDocument()
})

it.each(['closing', 'archived', 'deleting'] as const)('keeps a %s project detail read-only', async lifecycleState => {
  const project = { ...a, lifecycleState }
  const request = vi.fn((path: string) => Promise.resolve(path.includes('/overview') ? { project, availability: project.availability, counts: {}, activity: [], recent: [] } : path.includes('?') ? { items: [], page: 1, pageSize: 50, total: 0 } : project))
  mount(request as StreamingApiClient['request'], { route: { projectId: a.projectId, tab: 'overview' } })
  const edit = await screen.findByRole('button', { name: '编辑项目' })
  expect(edit).toBeDisabled()
  fireEvent.click(edit)
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

it('mounts the actual data directory and composes its dirty guard with global navigation', async () => {
  let guard: (() => Promise<boolean>) | null = null
  const request = vi.fn((path: string) => Promise.resolve(path.includes('/tables?') ? { items: [], page: 1, pageSize: 50, total: 0, sort: '-updatedAt' } : path.includes('?') ? { items: [a], total: 1 } : a))
  mount(request as StreamingApiClient['request'], { route: { projectId: a.projectId, tab: 'data' }, registerLeaveGuard: value => { guard = value } })
  await userEvent.click(await screen.findByRole('button', { name: '新建数据表' }))
  await userEvent.type(screen.getByLabelText('数据表名称'), '跨页面草稿')
  let leaving!: Promise<boolean>
  fireEvent.click(screen.getByRole('button', { name: '取消' }))
  expect(await screen.findByRole('alertdialog')).toHaveTextContent('放弃未保存')
  await userEvent.click(screen.getByRole('button', { name: '继续编辑' }))
  await act(async () => { leaving = guard!() })
  expect(await screen.findByRole('alertdialog')).toHaveTextContent('放弃未保存')
  await userEvent.click(screen.getByRole('button', { name: '继续编辑' }))
  expect(await leaving).toBe(false)
})

it('keeps a data form mounted across reconnect while refreshing the project facts', async () => {
  const request = vi.fn((path: string) => Promise.resolve(path.includes('/tables?') ? { items: [], total: 0, page: 1, pageSize: 50 } : path.includes('?') ? { items: [a], total: 1 } : a))
  const view = mount(request as StreamingApiClient['request'], { route: { projectId: a.projectId, tab: 'data' } })
  await userEvent.click(await screen.findByRole('button', { name: '新建数据表' }))
  await userEvent.type(screen.getByLabelText('数据表名称'), '保留草稿')
  const reconnect = deferred<unknown>()
  const newClient = { request: vi.fn(() => reconnect.promise), stream: vi.fn(), health: vi.fn() } as unknown as StreamingApiClient
  view.rerender(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ProjectsWorkspace {...view.values} instanceId="i2" client={newClient} /></QueryClientProvider>)
  expect(screen.getByLabelText('数据表名称')).toHaveValue('保留草稿')
  expect(screen.getByLabelText('数据表名称')).toBeVisible()
})


it('requests recent projects independently of restored all-directory search and excludes unopened items', async () => {
  sessionStorage.setItem('autoflow:projects-ui:w1', JSON.stringify({ mode: 'recent', query: '另一页', page: 2 }))
  const request = vi.fn(async (path: string) => ({ items: path.includes('pageSize=6') ? [{ ...a, lastOpenedAt: '2026-09-13T01:00:00Z' }, b] : [b], page: 1, pageSize: 50, total: 60, sort: '-lastOpenedAt' }))
  mount(request as StreamingApiClient['request'])
  expect(await screen.findByText('项目A')).toBeInTheDocument()
  expect(screen.queryByText('项目B')).not.toBeInTheDocument()
  expect(request.mock.calls.some(([path]) => { const params = new URL(path, 'http://local').searchParams; return params.get('pageSize') === '6' && params.get('page') === '1' && !params.get('query') && params.get('lifecycleState') === 'active' })).toBe(true)
  await userEvent.click(screen.getByRole('button', { name: '查看全部项目' }))
  expect(await screen.findByText('项目B')).toBeInTheDocument()
  expect(screen.getByLabelText('搜索项目')).toHaveValue('另一页')
})

it('renders the single manual detail for a manual-item route instead of the run directory', async () => {
  const manualItemId = '00000000-0000-4000-8000-00000000000d'
  const request = vi.fn(async (path: string) => {
    if (path.includes('/manual-items/')) return { manualItemId, projectId: a.projectId, taskId: '00000000-0000-4000-8000-00000000000e', runId: '00000000-0000-4000-8000-00000000000c', instanceId: null, checkpointRevision: 1, status: 'waiting', statusRevision: 1, expiresAt: null, allowedTargets: [], resumeStarted: false, reason: '等待人工现场', createdAt: '2026-09-18T00:00:00Z', updatedAt: '2026-09-18T00:00:00Z' }
    if (path.includes('/tasks/')) return { automationName: '资料整理', batchStartedAt: null, parameterDefinitions: [], task: { taskId: '00000000-0000-4000-8000-00000000000e', projectId: a.projectId, batchId: '00000000-0000-4000-8000-00000000000c', runId: '00000000-0000-4000-8000-00000000000c', runRequestId: '00000000-0000-4000-8000-00000000000c', status: 'waiting_manual', statusRevision: 1, inputSnapshotId: null, taskOrdinal: 1, automationName: '资料整理', batchStartedAt: null, inputIdentifier: 'R001', endNodeName: null, createdAt: '2026-09-18T00:00:00Z', completedAt: null }, inputSnapshot: { inputSnapshotId: 'snapshot', taskId: '00000000-0000-4000-8000-00000000000e', batchId: '00000000-0000-4000-8000-00000000000c', parameters: {}, inputs: [], capturedAt: '2026-09-18T00:00:00Z' }, run: null }
    if (path.includes(`/projects/${a.projectId}`)) return { ...a } as ProjectView
    return { items: [], page: 1, pageSize: 50, total: 0, sort: '-lastOpenedAt' }
  })
  mount(request as unknown as StreamingApiClient['request'], { route: { projectId: a.projectId, tab: 'runs', runView: 'manual', manualItemId } })
  expect(await screen.findByRole('heading', { level: 1, name: /等待人工现场/ })).toBeVisible()
  expect(screen.getByRole('region', { name: '处理方式' })).toBeVisible()
  expect(screen.queryByRole('heading', { name: '运行记录' })).not.toBeInTheDocument()
})
