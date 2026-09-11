import '@testing-library/jest-dom/vitest'
import { screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ApiClientError } from '../../../shared/api/client'
import type { ModelApi } from '../api'
import { createModelApi } from '../api'
import { modelKeys, type ModelDiscoveryRead, type ModelProviderRead } from '../model'
import { ProviderWizard } from '../components/ProviderWizard'
import { deferred, renderModelUi } from './test-utils'

const provider = { id: 'provider-1', name: 'Local', presetId: 'ollama', providerKind: 'openai-compatible', baseUrl: 'http://127.0.0.1:11434/v1', apiKeyConfigured: true, enabled: true, description: '', models: [], connectionStatus: 'connected', lastCheckedAt: null, lastCheckLatencyMs: null, lastCheckMessage: null, createdAt: '2026-09-12T00:00:00Z', updatedAt: '2026-09-12T00:00:00Z' } as ModelProviderRead
const discovery = { ok: true, items: [{ modelKey: 'visible', displayName: 'Visible', ownedBy: null, contextWindow: null }, { modelKey: 'hidden', displayName: 'Hidden', ownedBy: null, contextWindow: 8192 }], total: 2, latencyMs: 5, endpoint: 'http://127.0.0.1:11434/v1/models', message: '发现 2 个模型' } as ModelDiscoveryRead

function api(overrides: Partial<ModelApi> = {}): ModelApi {
  return { listProviders: vi.fn(), getProvider: vi.fn(), previewConnection: vi.fn().mockResolvedValue(discovery), connect: vi.fn().mockResolvedValue(provider), updateProvider: vi.fn().mockResolvedValue(provider), updateConnection: vi.fn().mockResolvedValue(provider), removeProvider: vi.fn(), testProvider: vi.fn(), discoverModels: vi.fn(), testModel: vi.fn(), createModel: vi.fn(), updateModel: vi.fn(), removeModel: vi.fn(), listOptions: vi.fn(), ...overrides }
}

describe('ProviderWizard', () => {
  it('sends JSON writes with an explicit content type', async () => {
    const request = vi.fn().mockResolvedValue(provider)
    const modelApi = createModelApi({ request, health: vi.fn() })
    await modelApi.updateProvider('provider-1', { name: 'Local', enabled: true, description: '' })
    expect(request).toHaveBeenCalledWith('/api/v1/model-providers/provider-1', expect.objectContaining({
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: 'Local', enabled: true, description: '' }),
    }))
  })

  it('edits metadata directly and switches to connection save only after connection changes', async () => {
    const modelApi = api()
    const { user } = renderModelUi(<ProviderWizard open instanceId="test" provider={provider} api={modelApi} onOpenChange={vi.fn()} onSaved={vi.fn()} />)
    expect(screen.getByText(/连接信息/)).toHaveAttribute('aria-current', 'step')
    expect(screen.queryByRole('button', { name: '上一步' })).not.toBeInTheDocument()
    await user.clear(screen.getByLabelText('供应商名称')); await user.type(screen.getByLabelText('供应商名称'), '新名称')
    expect(screen.getByRole('button', { name: '保存修改' })).toBeEnabled()
    await user.clear(screen.getByLabelText('服务地址')); await user.type(screen.getByLabelText('服务地址'), 'http://127.0.0.1:11435/v1')
    expect(screen.getByRole('button', { name: '测试并保存' })).toBeEnabled()
    await user.click(screen.getByRole('button', { name: '测试并保存' }))
    await waitFor(() => expect(modelApi.updateConnection).toHaveBeenCalled())
    expect(vi.mocked(modelApi.updateConnection).mock.calls[0]![1]).not.toHaveProperty('apiKey')
  })

  it('saves metadata without testing the connection', async () => {
    const modelApi = api()
    const { user } = renderModelUi(<ProviderWizard open instanceId="test" provider={provider} api={modelApi} onOpenChange={vi.fn()} onSaved={vi.fn()} />)
    await user.clear(screen.getByLabelText('供应商名称')); await user.type(screen.getByLabelText('供应商名称'), '新名称')
    await user.click(screen.getByRole('button', { name: '保存修改' }))
    await waitFor(() => expect(modelApi.updateProvider).toHaveBeenCalledWith('provider-1', { name: '新名称', enabled: true, description: '' }))
    expect(modelApi.updateConnection).not.toHaveBeenCalled()
  })

  it('keeps the custom entry available when common-provider search has no result', async () => {
    const { user } = renderModelUi(<ProviderWizard open instanceId="test" api={api()} onOpenChange={vi.fn()} onSaved={vi.fn()} />)
    await user.type(screen.getByLabelText('搜索供应商目录'), '不存在的供应商')
    expect(screen.getByRole('button', { name: /自定义 OpenAI 兼容接口/ })).toBeInTheDocument()
  })

  it('sends an explicitly cleared optional key', async () => {
    const modelApi = api()
    const { user } = renderModelUi(<ProviderWizard open instanceId="test" provider={provider} api={modelApi} onOpenChange={vi.fn()} onSaved={vi.fn()} />)
    await user.type(screen.getByLabelText('API Key（可选）'), 'x'); await user.clear(screen.getByLabelText('API Key（可选）'))
    await user.click(screen.getByRole('button', { name: '测试并保存' }))
    await waitFor(() => expect(modelApi.updateConnection).toHaveBeenCalledWith('provider-1', expect.objectContaining({ apiKey: '' })))
  })

  it('previews then saves zero models', async () => {
    const modelApi = api({ previewConnection: vi.fn().mockResolvedValue({ ...discovery, items: [], total: 0 }) })
    const { user } = renderModelUi(<ProviderWizard open instanceId="test" api={modelApi} onOpenChange={vi.fn()} onSaved={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: '下一步' })); await user.type(screen.getByLabelText('API Key'), 'key'); await user.click(screen.getByRole('button', { name: '测试连接' }))
    expect(await screen.findByText('连接测试成功')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '保存供应商' }))
    await waitFor(() => expect(modelApi.connect).toHaveBeenCalledWith(expect.objectContaining({ selectedModels: [] })))
  })

  it('selects all discovered models even when search hides one', async () => {
    const modelApi = api()
    const { user } = renderModelUi(<ProviderWizard open instanceId="test" api={modelApi} onOpenChange={vi.fn()} onSaved={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: '下一步' })); await user.type(screen.getByLabelText('API Key'), 'key'); await user.click(screen.getByRole('button', { name: '测试连接' })); await screen.findByText('连接测试成功')
    await user.type(screen.getByLabelText('搜索发现的模型'), 'Visible'); await user.click(screen.getByRole('button', { name: '选择全部' })); await user.click(screen.getByRole('button', { name: '保存供应商和 2 个模型' }))
    await waitFor(() => expect(vi.mocked(modelApi.connect).mock.calls[0]![0].selectedModels).toHaveLength(2))
  })

  it('locks closing while preview is pending and keeps input after failure', async () => {
    const pending = deferred<ModelDiscoveryRead>()
    const onOpenChange = vi.fn()
    const modelApi = api({ previewConnection: vi.fn(() => pending.promise) })
    const { user } = renderModelUi(<ProviderWizard open instanceId="test" api={modelApi} onOpenChange={onOpenChange} onSaved={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: '下一步' })); await user.type(screen.getByLabelText('API Key'), 'keep-me'); await user.click(screen.getByRole('button', { name: '测试连接' })); await user.keyboard('{Escape}')
    expect(onOpenChange).not.toHaveBeenCalled()
    pending.reject(new Error('连接失败'))
    expect(await screen.findByText('连接失败')).toBeInTheDocument()
    expect(screen.getByLabelText('API Key')).toHaveValue('keep-me')
  })

  it('keeps every connection control locked during an in-flight preview', async () => {
    const pending = deferred<ModelDiscoveryRead>()
    const modelApi = api({ previewConnection: vi.fn(() => pending.promise) })
    const { user } = renderModelUi(<ProviderWizard open instanceId="test" api={modelApi} onOpenChange={vi.fn()} onSaved={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: '下一步' }))
    await user.type(screen.getByLabelText('API Key'), 'key')
    await user.click(screen.getByRole('button', { name: '测试连接' }))
    expect(screen.getByLabelText('供应商名称')).toBeDisabled()
    expect(screen.getByLabelText('接口协议')).toBeDisabled()
    expect(screen.getByLabelText('服务地址')).toBeDisabled()
    expect(screen.getByLabelText('API Key')).toBeDisabled()
    expect(screen.getByLabelText('说明')).toBeDisabled()
    expect(screen.getByLabelText('启用供应商')).toBeDisabled()
    expect(modelApi.previewConnection).toHaveBeenCalledTimes(1)
    pending.resolve(discovery)
    expect(await screen.findByText('连接测试成功')).toBeInTheDocument()
  })

  it('cancels the exact instance discovery key and discards its late result', async () => {
    const late = deferred<ModelDiscoveryRead>()
    const modelApi = api()
    const { user, queryClient } = renderModelUi(<ProviderWizard open instanceId="instance-a" provider={provider} api={modelApi} onOpenChange={vi.fn()} onSaved={vi.fn()} />)
    const key = modelKeys.discovery('instance-a', provider.id)
    const cancellation = vi.spyOn(queryClient, 'cancelQueries')
    void queryClient.fetchQuery({ queryKey: key, queryFn: () => late.promise }).catch(() => undefined)
    await user.clear(screen.getByLabelText('服务地址'))
    await user.type(screen.getByLabelText('服务地址'), 'http://127.0.0.1:11435/v1')
    await user.click(screen.getByRole('button', { name: '测试并保存' }))
    await waitFor(() => expect(modelApi.updateConnection).toHaveBeenCalled())
    expect(cancellation).toHaveBeenCalledWith({ queryKey: key, exact: true })
    late.resolve(discovery)
    await waitFor(() => expect(queryClient.getQueryData(key)).toBeUndefined())
  })

  it('keeps the model step and selection when final connect fails, then retries', async () => {
    const first = deferred<ModelProviderRead>()
    const connect = vi.fn().mockImplementationOnce(() => first.promise).mockResolvedValue(provider)
    const modelApi = api({ connect })
    const { user } = renderModelUi(<ProviderWizard open instanceId="test" api={modelApi} onOpenChange={vi.fn()} onSaved={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: '下一步' }))
    await user.type(screen.getByLabelText('API Key'), 'key')
    await user.click(screen.getByRole('button', { name: '测试连接' }))
    await screen.findByText('连接测试成功')
    expect(screen.getByText('上下文长度未知')).toBeInTheDocument()
    expect(screen.getByText('8,192 tokens')).toBeInTheDocument()
    await user.click(screen.getByLabelText('选择 Visible'))
    await user.click(screen.getByRole('button', { name: '保存供应商和 1 个模型' }))
    first.reject(new Error('选择的模型已从远端目录消失'))
    expect(await screen.findByRole('alert')).toHaveTextContent('选择的模型已从远端目录消失')
    expect(screen.getByText(/选择模型/)).toHaveAttribute('aria-current', 'step')
    expect(screen.getByLabelText('选择 Visible')).toBeChecked()
    await user.click(screen.getByRole('button', { name: '保存供应商和 1 个模型' }))
    await waitFor(() => expect(connect).toHaveBeenCalledTimes(2))
  })

  it('refreshes current-instance lists after a changed connection while preserving the draft', async () => {
    const changed = new ApiClientError('供应商已被其他操作更新', 409, 'MODEL_PROVIDER_CHANGED')
    const modelApi = api({ updateConnection: vi.fn().mockRejectedValue(changed) })
    const { user, queryClient } = renderModelUi(<ProviderWizard open instanceId="instance-a" provider={provider} api={modelApi} onOpenChange={vi.fn()} onSaved={vi.fn()} />)
    const invalidation = vi.spyOn(queryClient, 'invalidateQueries')
    await user.clear(screen.getByLabelText('供应商名称'))
    await user.type(screen.getByLabelText('供应商名称'), '保留的草稿')
    await user.clear(screen.getByLabelText('服务地址'))
    await user.type(screen.getByLabelText('服务地址'), 'http://127.0.0.1:11435/v1')
    await user.click(screen.getByRole('button', { name: '测试并保存' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('供应商已被其他操作更新')
    expect(screen.getByLabelText('供应商名称')).toHaveValue('保留的草稿')
    expect(screen.getByLabelText('服务地址')).toHaveValue('http://127.0.0.1:11435/v1')
    await waitFor(() => {
      expect(invalidation).toHaveBeenCalledWith({ queryKey: modelKeys.providers('instance-a'), exact: true })
      expect(invalidation).toHaveBeenCalledWith({ queryKey: modelKeys.options('instance-a'), exact: true })
    })
    expect(invalidation).not.toHaveBeenCalledWith({ queryKey: modelKeys.providers('other-instance'), exact: true })
  })
})
