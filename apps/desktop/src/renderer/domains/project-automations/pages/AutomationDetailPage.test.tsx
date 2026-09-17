import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApiClientError, type ApiRequestInit, type StreamingApiClient } from '../../../shared/api/client'
import { choiceTestEnvironment, chooseOption } from '../../../shared/testing/choice-user'
import type { Automation } from '../types'
import { AutomationDetailPage, type AutomationDetailPageProps } from './AutomationDetailPage'

choiceTestEnvironment()
const stored = new Map<string, string>()
beforeEach(() => { stored.clear(); vi.stubGlobal('localStorage', { getItem: (key: string) => stored.get(key) ?? null, setItem: (key: string, value: string) => stored.set(key, value), removeItem: (key: string) => stored.delete(key) }) })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
const automation: Automation = { name: '原名称', description: '', workflowId: 'wf', inputPlan: { inputs: [] }, parameterSchema: [], environmentPolicy: { source: 'newFromProfile' }, runPolicy: { maxTasks: 1, concurrency: 1, maxLiveInstances: 1, continueAfterFailure: false, automaticExecutionTimeoutSeconds: 900, manualDeadlineSeconds: 900 }, automationId: 'a', projectId: 'p', managementRevision: 3, createdAt: '2026-09-01T00:00:00Z', updatedAt: '2026-09-01T00:00:00Z' }
const resources = (path: string) => path === '/api/v1/workflows' ? { items: [{ workflowId: 'wf', name: '工作流', revision: 1, updatedAt: '', validation: { status: 'ready', runnable: true, issues: [] } }] } : path === '/api/v1/model-providers' ? { items: [], total: 0 } : path === '/api/v1/profiles' ? { items: [], total: 0 } : path === '/api/v1/proxy-options' ? { proxies: [], pools: [] } : path.includes('/tables?') ? { items: [], total: 0, page: 1, pageSize: 200, sort: 'name' } : undefined
function mount(request: StreamingApiClient['request'], override: Partial<AutomationDetailPageProps> = {}) {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const props: AutomationDetailPageProps = { workspaceKey: 'w', instanceId: 'i', projectId: 'p', client: { request, stream: vi.fn(), health: vi.fn() }, disabled: false, readOnly: false, onCreated: vi.fn(), registerLeaveGuard: vi.fn(), ...override }
  const tree = (next: Partial<AutomationDetailPageProps> = {}) => <QueryClientProvider client={cache}><AutomationDetailPage {...props} {...next}/></QueryClientProvider>
  const view = render(tree())
  return { ...view, props, cache, update: (next: Partial<AutomationDetailPageProps>) => view.rerender(tree(next)) }
}

it('submits one normalized payload containing values edited across all four tabs', async () => {
  const writes: ApiRequestInit[] = []
  const request = vi.fn(async (path: string, init?: ApiRequestInit) => {
    const found = resources(path); if (found) return found
    if (init?.method === 'POST') { writes.push(init); return { ...automation, ...(init.body as object) } }
    throw new Error(`unexpected ${path}`)
  }) as StreamingApiClient['request']
  const { props } = mount(request)
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText('自动化名称'), ' 自动运行 ')
  await chooseOption(user, screen.getByRole('combobox', { name: '关联工作流' }), 'wf')
  await user.click(screen.getByRole('tab', { name: '输入与参数' })); await user.click(screen.getByRole('button', { name: '新增参数' })); await user.type(screen.getByLabelText(/^参数名称/), '次数'); await chooseOption(user, screen.getByRole('combobox', { name: '参数类型 次数' }), 'number'); await user.type(screen.getByLabelText('默认值 次数'), '12')
  await user.click(screen.getByRole('tab', { name: '资源与环境' })); await user.click(screen.getByRole('radio', { name: '不使用代理' }))
  await user.click(screen.getByRole('tab', { name: '运行设置' })); await user.clear(screen.getByLabelText('最大任务数')); await user.type(screen.getByLabelText('最大任务数'), '7'); await user.clear(screen.getByLabelText('单任务超时（分钟）')); await user.type(screen.getByLabelText('单任务超时（分钟）'), '2.5')
  await user.click(screen.getByRole('button', { name: '保存配置' }))
  await waitFor(() => expect(props.onCreated).toHaveBeenCalledWith('a'))
  expect(writes).toHaveLength(1)
  expect(writes[0].body).toMatchObject({ name: '自动运行', workflowId: 'wf', parameterSchema: [{ name: '次数', type: 'number', defaultValue: 12 }], environmentPolicy: { source: 'newFromProfile', proxyOverride: { mode: 'none' } }, runPolicy: { maxTasks: 7, automaticExecutionTimeoutSeconds: 150 } })
})

it('keeps the edit draft through background refresh and a 409 until latest data is explicitly accepted', async () => {
  let current = automation
  const request = vi.fn(async (path: string, init?: ApiRequestInit) => {
    const found = resources(path); if (found) return found
    if (path.endsWith('/validation')) return { status: 'ready', valid: true, runnable: true, issues: [], capabilityRequirements: [], checkedAt: '' }
    if (init?.method === 'PUT') throw new ApiClientError('自动化已变化', 409, 'REVISION_CONFLICT')
    if (path.endsWith('/automations/a')) return current
    throw new Error(`unexpected ${path}`)
  }) as StreamingApiClient['request']
  const view = mount(request, { automationId: 'a' }); const user = userEvent.setup()
  const name = await screen.findByLabelText('自动化名称')
  await user.clear(name); await user.type(name, '我的草稿')
  current = { ...automation, name: '服务端最新', managementRevision: 4 }
  await view.cache.invalidateQueries()
  expect(name).toHaveValue('我的草稿')
  await user.click(screen.getByRole('button', { name: '保存配置' }))
  expect(await screen.findByText(/自动化资料已变化，你的输入已保留/)).toBeVisible()
  expect(name).toHaveValue('我的草稿')
  await user.click(screen.getByRole('button', { name: '载入最新资料重新编辑' })); await user.click(screen.getByRole('button', { name: '载入最新资料' }))
  await waitFor(() => expect(screen.getByLabelText('自动化名称')).toHaveValue('服务端最新'))
})

it('keeps the draft and ignores a late save response after reconnecting to another instance', async () => {
  let resolveSave!: (value: Automation) => void
  const save = new Promise<Automation>(resolve => { resolveSave = resolve })
  const request = vi.fn(async (path: string, init?: ApiRequestInit) => {
    const found = resources(path); if (found) return found
    if (path.endsWith('/validation')) return { status: 'ready', valid: true, runnable: true, issues: [], capabilityRequirements: [], checkedAt: '' }
    if (init?.method === 'PUT') return save
    if (path.endsWith('/automations/a')) return automation
    throw new Error(`unexpected ${path}`)
  }) as StreamingApiClient['request']
  const view = mount(request, { automationId: 'a' }); const user = userEvent.setup()
  const name = await screen.findByLabelText('自动化名称'); await user.clear(name); await user.type(name, '重连草稿'); await user.click(screen.getByRole('button', { name: '保存配置' }))
  view.update({ automationId: 'a', instanceId: 'i2' })
  expect(screen.getByLabelText('自动化名称')).toHaveValue('重连草稿')
  resolveSave({ ...automation, name: '迟到保存结果', managementRevision: 4 })
  await Promise.resolve(); await Promise.resolve()
  expect(screen.getByLabelText('自动化名称')).toHaveValue('重连草稿')
  expect(view.props.onCreated).not.toHaveBeenCalled()
})
