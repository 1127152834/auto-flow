import '@testing-library/jest-dom/vitest'
import { screen, waitFor, within } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import type { ModelApi } from '../api'
import type { ModelProvider } from '../model'
import { ModelManagementPage } from '../pages/ModelManagementPage'
import { deferred, renderModelUi } from './test-utils'

const model = { id: 'm1', providerId: 'p1', modelKey: 'sample-chat', displayName: 'Sample chat', contextWindow: 8192, tagsJson: ['中文'], description: '', enabled: true, createdAt: '', updatedAt: '' }
const first: ModelProvider = { id: 'p1', name: 'First', presetId: 'custom', providerKind: 'openai-compatible', baseUrl: 'http://localhost/v1', apiKeyConfigured: false, enabled: true, description: '', models: [model], connectionStatus: 'untested', lastCheckedAt: null, lastCheckLatencyMs: null, lastCheckMessage: null, createdAt: '', updatedAt: '' }
const second: ModelProvider = { ...first, id: 'p2', name: 'Second', models: [{ ...model, id: 'm2', providerId: 'p2' }] }
function api(overrides: Partial<ModelApi> = {}): ModelApi {
  return { listProviders: vi.fn().mockResolvedValue({ items: [first, second], total: 2 }), getProvider: vi.fn(), previewConnection: vi.fn(), connect: vi.fn(), updateProvider: vi.fn().mockResolvedValue(first), updateConnection: vi.fn(), removeProvider: vi.fn().mockResolvedValue(undefined), testProvider: vi.fn(), discoverModels: vi.fn().mockResolvedValue({ ok: true, items: [], total: 0, latencyMs: 1, message: '' }), testModel: vi.fn(), createModel: vi.fn(), updateModel: vi.fn(), removeModel: vi.fn(), listOptions: vi.fn(), ...overrides }
}

it('preserves selected details when supplier search hides the item, and preserves model filters on selection', async () => {
  const { user } = renderModelUi(<ModelManagementPage api={api()} instanceId="one" />)
  await screen.findByRole('columnheader', { name: '模型' })
  expect(screen.getAllByRole('columnheader')).toHaveLength(5)
  await user.type(screen.getByPlaceholderText('搜索供应商'), 'Second')
  expect(within(screen.getByRole('region', { name: '供应商详情' })).getByText('First')).toBeInTheDocument()
  await user.type(screen.getByPlaceholderText('搜索模型名称、标识或标签'), 'missing')
  await user.click(screen.getByRole('button', { name: /Second/ }))
  expect(screen.getByPlaceholderText('搜索模型名称、标识或标签')).toHaveValue('missing')
})

it('discards late row-test feedback after switching suppliers', async () => {
  const pending = deferred<Awaited<ReturnType<ModelApi['testModel']>>>()
  const { user } = renderModelUi(<ModelManagementPage api={api({ testModel: vi.fn(() => pending.promise) })} instanceId="one" />)
  await user.click(await screen.findByRole('button', { name: 'Sample chat 测试模型' }))
  await user.click(screen.getByRole('button', { name: /Second/ }))
  pending.resolve({ ok: true, modelKey: 'sample-chat', latencyMs: 1, outputPreview: 'stale output', reasoningPreview: '', message: '' })
  await waitFor(() => expect(screen.getByRole('button', { name: '测试连接' })).toBeEnabled())
  expect(screen.queryByText(/stale output/)).not.toBeInTheDocument()
})

it('discards late row-test feedback after refresh removes the selected supplier', async () => {
  const pending = deferred<Awaited<ReturnType<ModelApi['testModel']>>>()
  const modelApi = api({ testModel: vi.fn(() => pending.promise) })
  const { user, queryClient } = renderModelUi(<ModelManagementPage api={modelApi} instanceId="one" />)
  await user.click(await screen.findByRole('button', { name: 'Sample chat 测试模型' }))
  vi.mocked(modelApi.listProviders).mockResolvedValue({ items: [second], total: 1 })
  await queryClient.invalidateQueries({ queryKey: ['model-providers', 'one'] })
  await waitFor(() => expect(within(screen.getByRole('region', { name: '供应商详情' })).getByText('Second')).toBeInTheDocument())
  pending.resolve({ ok: true, modelKey: 'sample-chat', latencyMs: 1, outputPreview: 'deleted provider output', reasoningPreview: '', message: '' })
  await waitFor(() => expect(screen.getByRole('button', { name: '测试连接' })).toBeEnabled())
  expect(screen.queryByText(/deleted provider output/)).not.toBeInTheDocument()
})

it('opens the same wizard from both add entries and sync-add discovers without creating a model', async () => {
  const modelApi = api()
  const { user, queryClient } = renderModelUi(<ModelManagementPage api={modelApi} instanceId="one" />)
  await screen.findByRole('columnheader', { name: '模型' })
  await user.click(screen.getByRole('button', { name: '添加供应商' }))
  expect(screen.getByRole('dialog', { name: '添加供应商' })).toBeInTheDocument()
  await user.keyboard('{Escape}')
  await user.click(screen.getByRole('button', { name: '添加模型供应商' }))
  expect(screen.getByRole('dialog', { name: '添加供应商' })).toBeInTheDocument()
  await user.keyboard('{Escape}')
  queryClient.setQueryData(['model-provider-discovery', 'one', 'p1'], { ok: true, items: [], total: 0, latencyMs: 1, endpoint: '', message: '' })
  await user.click(screen.getByRole('button', { name: '同步并添加' }))
  await waitFor(() => expect(modelApi.discoverModels).toHaveBeenCalledWith('p1', expect.any(AbortSignal)))
  expect(modelApi.createModel).not.toHaveBeenCalled()
})

it('renders retry after list failure and then the empty state', async () => {
  const listProviders = vi.fn().mockRejectedValueOnce(new Error('列表读取失败')).mockResolvedValue({ items: [], total: 0 })
  const { user } = renderModelUi(<ModelManagementPage api={api({ listProviders })} instanceId="one" />)
  await user.click(await screen.findByRole('button', { name: '重试' }))
  expect(await screen.findByText('还没有模型供应商')).toBeInTheDocument()
})

it('invalidates usable options on disable and selects the remaining supplier after deletion', async () => {
  const modelApi = api()
  const { user, queryClient } = renderModelUi(<ModelManagementPage api={modelApi} instanceId="one" />)
  queryClient.setQueryData(['model-options', 'one'], { items: ['existing'], total: 1 })
  await user.click(await screen.findByRole('button', { name: '供应商更多操作' }))
  await user.click(screen.getByRole('menuitem', { name: '停用供应商' }))
  await waitFor(() => expect(modelApi.updateProvider).toHaveBeenCalledWith('p1', { name: 'First', description: '', enabled: false }))
  await waitFor(() => expect(queryClient.getQueryState(['model-options', 'one'])?.isInvalidated).toBe(true))
  vi.mocked(modelApi.listProviders).mockResolvedValue({ items: [second], total: 1 })
  await user.click(screen.getByRole('button', { name: '供应商更多操作' }))
  await user.click(screen.getByRole('menuitem', { name: '删除供应商' }))
  await user.click(screen.getByRole('button', { name: '确认删除' }))
  await waitFor(() => expect(within(screen.getByRole('region', { name: '供应商详情' })).getByText('Second')).toBeInTheDocument())
  expect(modelApi.removeProvider).toHaveBeenCalledWith('p1')
})

it('retains the workspace when a background refresh fails', async () => {
  const modelApi = api()
  const { queryClient } = renderModelUi(<ModelManagementPage api={modelApi} instanceId="one" />)
  await screen.findByRole('columnheader', { name: '模型' })
  vi.mocked(modelApi.listProviders).mockRejectedValue(new Error('暂时无法读取'))
  await queryClient.invalidateQueries({ queryKey: ['model-providers', 'one'] })
  expect(await screen.findByText('刷新失败：暂时无法读取')).toBeInTheDocument()
  expect(screen.getByRole('columnheader', { name: '模型' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '重试刷新' })).toBeInTheDocument()
})

it('clears stale connection feedback after saving the provider', async () => {
  const modelApi = api({ testProvider: vi.fn().mockRejectedValue(new Error('旧连接不可用')) })
  const { user } = renderModelUi(<ModelManagementPage api={modelApi} instanceId="one" />)
  await user.click(await screen.findByRole('button', { name: '测试连接' }))
  await screen.findByText('旧连接不可用')
  await user.click(screen.getByRole('button', { name: '编辑' }))
  await user.click(screen.getByRole('button', { name: '保存修改' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(screen.queryByText('旧连接不可用')).not.toBeInTheDocument()
})
