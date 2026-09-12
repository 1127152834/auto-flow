import '@testing-library/jest-dom/vitest'
import {chooseOption,choiceTestEnvironment} from '../../../shared/testing/choice-user'
choiceTestEnvironment()
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ModelApi } from '../api'
import type { AiModel, ModelDiscoveryRead, ModelProvider, ModelTestResult } from '../model'
import { ModelEditor } from '../components/ModelEditor'
import { ModelDeleteDialog } from '../components/ModelDeleteDialog'
import { deferred, renderModelUi } from './test-utils'
import { ApiClientError } from '../../../shared/api/client'

const provider = { id: 'provider-1', name: 'Local', presetId: 'ollama', providerKind: 'openai-compatible', baseUrl: 'http://localhost:11434/v1', apiKeyConfigured: false, enabled: true, description: '', models: [], connectionStatus: 'connected', lastCheckedAt: null, lastCheckLatencyMs: null, lastCheckMessage: null, createdAt: '2026-09-12T00:00:00Z', updatedAt: '2026-09-12T00:00:00Z' } as ModelProvider
const model = { id: 'model-1', providerId: provider.id, modelKey: 'qwen3', displayName: 'Qwen 3', tagsJson: ['推理'], contextWindow: 32768, enabled: true, description: '旧说明', createdAt: '2026-09-12T00:00:00Z', updatedAt: '2026-09-12T00:00:00Z' } as AiModel
const discovery = { ok: true, items: [{ modelKey: 'known', displayName: 'Known', ownedBy: null, contextWindow: 8192 }, { modelKey: 'unknown', displayName: 'Unknown', ownedBy: null, contextWindow: null }], total: 2, latencyMs: 1, endpoint: '/models', message: '' } as ModelDiscoveryRead

function api(overrides: Partial<ModelApi> = {}): ModelApi {
  return { listProviders: vi.fn(), getProvider: vi.fn(), previewConnection: vi.fn(), connect: vi.fn(), updateProvider: vi.fn(), updateConnection: vi.fn(), removeProvider: vi.fn(), testProvider: vi.fn(), discoverModels: vi.fn().mockResolvedValue(discovery), testModel: vi.fn(), createModel: vi.fn().mockResolvedValue(model), updateModel: vi.fn().mockResolvedValue(model), removeModel: vi.fn(), listOptions: vi.fn(), ...overrides }
}

describe('ModelEditor', () => {
  it('allows saving and closing while a model test is pending, and ignores its late result', async () => {
    const pending = deferred<ModelTestResult>()
    const onOpenChange = vi.fn()
    const modelApi = api({ testModel: vi.fn(() => pending.promise) })
    const first = renderModelUi(<ModelEditor open provider={provider} api={modelApi} instanceId="one" onOpenChange={onOpenChange} onSaved={vi.fn()} onRemoved={vi.fn()} />)
    const { user } = first
    await user.type(screen.getByLabelText('模型标识'), 'manual'); await user.type(screen.getByLabelText('显示名称'), 'Manual')
    await user.click(screen.getByRole('button', { name: '测试模型' }))
    expect(screen.getByRole('button', { name: '保存模型' })).toBeEnabled()
    await user.keyboard('{Escape}')
    expect(onOpenChange).toHaveBeenCalledWith(false)
    first.unmount()
    renderModelUi(<ModelEditor open provider={provider} api={modelApi} instanceId="one" onOpenChange={onOpenChange} onSaved={vi.fn()} onRemoved={vi.fn()} />)
    pending.resolve({ ok: true, modelKey: 'manual', latencyMs: 5, outputPreview: 'OLD', reasoningPreview: '', message: '' })
    await waitFor(() => expect(screen.queryByText('OLD')).not.toBeInTheDocument())
  })

  it('selects or manually enters an ID and preserves context when a candidate has none', async () => {
    const modelApi = api()
    const { user } = renderModelUi(<ModelEditor open provider={provider} api={modelApi} instanceId="one" onOpenChange={vi.fn()} onSaved={vi.fn()} onRemoved={vi.fn()} />)
    await screen.findByText('已发现 2 个模型')
    await chooseOption(user, screen.getByRole('combobox', {name:'模型标识'}), 'known')
    expect(screen.getByLabelText('上下文窗口')).toHaveValue('8192')
    expect(screen.getByLabelText('显示名称')).toHaveValue('Known')
    await chooseOption(user, screen.getByRole('combobox', {name:'模型标识'}), 'unknown')
    expect(screen.getByLabelText('上下文窗口')).toHaveValue('8192')
    expect(screen.getByLabelText('显示名称')).toHaveValue('Unknown')
    await user.clear(screen.getByLabelText('模型标识')); await user.type(screen.getByLabelText('模型标识'), 'custom{Enter}')
    expect(screen.getByLabelText('模型标识')).toHaveValue('custom')
  })

  it('normalizes tags on IME-safe Enter, blur, and save and validates context', async () => {
    const modelApi = api()
    const { user } = renderModelUi(<ModelEditor open provider={provider} api={modelApi} instanceId="one" onOpenChange={vi.fn()} onSaved={vi.fn()} onRemoved={vi.fn()} />)
    await user.type(screen.getByLabelText('模型标识'), 'manual'); await user.type(screen.getByLabelText('显示名称'), 'Manual')
    const tags = screen.getByLabelText('自定义标签')
    fireEvent.compositionStart(tags); fireEvent.change(tags, { target: { value: '本地' } }); fireEvent.keyDown(tags, { key: 'Enter', isComposing: true }); expect(tags).toHaveValue('本地')
    fireEvent.compositionEnd(tags); await user.type(tags, ', 推理，生产,推理{Enter}')
    expect(screen.getByText('本地')).toBeInTheDocument(); expect(screen.getAllByText('推理')).toHaveLength(1)
    await user.type(tags, '草稿'); await user.clear(screen.getByLabelText('上下文窗口')); await user.type(screen.getByLabelText('上下文窗口'), '-1')
    await user.click(screen.getByRole('button', { name: '保存模型' })); expect(await screen.findByRole('alert')).toHaveTextContent('正安全整数')
    await user.clear(screen.getByLabelText('上下文窗口')); await user.click(screen.getByRole('button', { name: '保存模型' }))
    await waitFor(() => expect(modelApi.createModel).toHaveBeenCalledWith(provider.id, expect.objectContaining({ contextWindow: null, tagsJson: ['本地', '推理', '生产', '草稿'] })))
  })

  it('keeps editing ID readonly, reports copy failure, and preserves draft when delete is cancelled', async () => {
    const { user } = renderModelUi(<ModelEditor open provider={provider} model={model} api={api()} instanceId="one" onOpenChange={vi.fn()} onSaved={vi.fn()} onRemoved={vi.fn()} />)
    vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValue(new Error('no'))
    expect(screen.getByLabelText('模型标识')).toHaveAttribute('readonly')
    await user.click(screen.getByRole('button', { name: '复制模型标识' })); expect(await screen.findByRole('status')).toHaveTextContent('复制未完成')
    await user.clear(screen.getByLabelText('显示名称')); await user.type(screen.getByLabelText('显示名称'), '草稿名')
    await user.click(screen.getByRole('button', { name: '从目录移除' })); await user.click(within(screen.getByRole('dialog', { name: '删除模型' })).getByRole('button', { name: '取消' }))
    expect(screen.getByLabelText('显示名称')).toHaveValue('草稿名')
    expect(screen.getByRole('button', { name: '从目录移除' })).toHaveFocus()
  })

  it('allows manual entry after discovery failure and disables refresh while reloading', async () => {
    const refresh = deferred<ModelDiscoveryRead>()
    const discoverModels = vi.fn().mockRejectedValueOnce(new Error('目录离线')).mockImplementationOnce(() => refresh.promise)
    const modelApi = api({ discoverModels })
    const { user } = renderModelUi(<ModelEditor open provider={provider} api={modelApi} instanceId="offline" onOpenChange={vi.fn()} onSaved={vi.fn()} onRemoved={vi.fn()} />)
    expect(await screen.findByText(/目录读取失败.*目录离线/)).toBeInTheDocument()
    await user.type(screen.getByLabelText('模型标识'), 'manual{Enter}'); await user.type(screen.getByLabelText('显示名称'), 'Manual')
    expect(screen.getByRole('button', { name: '保存模型' })).toBeEnabled()
    await user.click(screen.getByRole('button', { name: '刷新模型目录' }))
    expect(screen.getByRole('button', { name: '刷新模型目录' })).toBeDisabled()
    refresh.resolve(discovery)
    expect(await screen.findByText('已发现 2 个模型')).toBeInTheDocument()
  })

  it('locks the modal only while saving and disables model testing during save', async () => {
    const pending = deferred<AiModel>()
    const onOpenChange = vi.fn()
    const modelApi = api({ createModel: vi.fn(() => pending.promise) })
    const { user } = renderModelUi(<ModelEditor open provider={provider} api={modelApi} instanceId="save" onOpenChange={onOpenChange} onSaved={vi.fn()} onRemoved={vi.fn()} />)
    await user.type(screen.getByLabelText('模型标识'), 'manual'); await user.type(screen.getByLabelText('显示名称'), 'Manual')
    await user.click(screen.getByRole('button', { name: '保存模型' }))
    expect(screen.getByRole('button', { name: '测试模型' })).toBeDisabled()
    await user.keyboard('{Escape}')
    expect(onOpenChange).not.toHaveBeenCalled()
    pending.resolve(model)
  })

  it('actually saves while a model test is pending', async () => {
    const pendingTest = deferred<ModelTestResult>()
    const modelApi = api({ testModel: vi.fn(() => pendingTest.promise) })
    const onSaved = vi.fn()
    const { user } = renderModelUi(<ModelEditor open provider={provider} api={modelApi} instanceId="parallel" onOpenChange={vi.fn()} onSaved={onSaved} onRemoved={vi.fn()} />)
    await user.type(screen.getByLabelText('模型标识'), 'manual'); await user.type(screen.getByLabelText('显示名称'), 'Manual')
    await user.click(screen.getByRole('button', { name: '测试模型' }))
    await user.click(screen.getByRole('button', { name: '保存模型' }))
    await waitFor(() => expect(modelApi.createModel).toHaveBeenCalledWith(provider.id, expect.objectContaining({ modelKey: 'manual', displayName: 'Manual' })))
    expect(modelApi.testModel).toHaveBeenCalledWith(provider.id, { modelKey: 'manual' })
    expect(onSaved).toHaveBeenCalledWith(model)
  })

  it('blocks removal while an edit save is pending', async () => {
    const pendingSave = deferred<AiModel>()
    const modelApi = api({ updateModel: vi.fn(() => pendingSave.promise), removeModel: vi.fn() })
    const { user } = renderModelUi(<ModelEditor open provider={provider} model={model} api={modelApi} instanceId="edit-save" onOpenChange={vi.fn()} onSaved={vi.fn()} onRemoved={vi.fn()} />)
    await user.clear(screen.getByLabelText('显示名称')); await user.type(screen.getByLabelText('显示名称'), '保存中')
    await user.click(screen.getByRole('button', { name: '保存修改' }))
    const remove = screen.getByRole('button', { name: '从目录移除' })
    expect(remove).toBeDisabled()
    await user.click(remove)
    expect(screen.queryByRole('dialog', { name: '删除模型' })).not.toBeInTheDocument()
    expect(modelApi.updateModel).toHaveBeenCalledTimes(1)
    expect(modelApi.removeModel).not.toHaveBeenCalled()
    pendingSave.resolve(model)
  })

  it('rejects an old A result after switching A to B and back to A', async () => {
    const pending = deferred<ModelTestResult>()
    const modelApi = api({ testModel: vi.fn(() => pending.promise) })
    const { user } = renderModelUi(<ModelEditor open provider={provider} api={modelApi} instanceId="generation" onOpenChange={vi.fn()} onSaved={vi.fn()} onRemoved={vi.fn()} />)
    const id = screen.getByLabelText('模型标识')
    await user.type(id, 'A'); await user.keyboard('{Escape}'); await user.click(screen.getByRole('button', { name: '测试模型' }))
    await user.clear(id); await user.type(id, 'B'); await user.clear(id); await user.type(id, 'A')
    pending.resolve({ ok: true, modelKey: 'A', latencyMs: 1, outputPreview: '过期结果', reasoningPreview: '', message: '' })
    await waitFor(() => expect(screen.queryByText('过期结果')).not.toBeInTheDocument())
    expect(screen.getByText('尚未测试')).toBeInTheDocument()
  })

  it('uses the frozen 285px summary track for split layout', () => {
    renderModelUi(<ModelEditor open provider={provider} api={api()} instanceId="layout" onOpenChange={vi.fn()} onSaved={vi.fn()} onRemoved={vi.fn()} />)
    expect(screen.getByRole('region', { name: '添加模型内容' })).toHaveClass('md:grid-cols-[285px_minmax(0,1fr)]')
  })

  it('lets page-level locks block a delete mutation', async () => {
    const modelApi = api({ removeModel: vi.fn() })
    const { user } = renderModelUi(<ModelDeleteDialog open blocked model={model} api={modelApi} instanceId="blocked" onOpenChange={vi.fn()} onRemoved={vi.fn()} />)
    const confirm = screen.getByRole('button', { name: '确认移除' })
    expect(confirm).toBeDisabled()
    await user.click(confirm)
    expect(modelApi.removeModel).not.toHaveBeenCalled()
  })

  it('keeps the draft and refreshes only current-instance lists after a 404 save conflict', async () => {
    const error = new ApiClientError('模型已不存在', 404, 'MODEL_NOT_FOUND')
    const modelApi = api({ updateModel: vi.fn().mockRejectedValue(error) })
    const rendered = renderModelUi(<ModelEditor open provider={provider} model={model} api={modelApi} instanceId="current-instance" onOpenChange={vi.fn()} onSaved={vi.fn()} onRemoved={vi.fn()} />)
    const invalidate = vi.spyOn(rendered.queryClient, 'invalidateQueries')
    await rendered.user.clear(screen.getByLabelText('显示名称')); await rendered.user.type(screen.getByLabelText('显示名称'), '保留的草稿')
    await rendered.user.click(screen.getByRole('button', { name: '保存修改' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('模型已不存在')
    expect(screen.getByLabelText('显示名称')).toHaveValue('保留的草稿')
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['model-providers', 'current-instance'], exact: true })
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['model-options', 'current-instance'], exact: true })
    expect(invalidate).not.toHaveBeenCalledWith(expect.objectContaining({ queryKey: expect.arrayContaining(['other-instance']) }))
  })

  it('associates the model ID label and prevents composing Enter from submitting', () => {
    renderModelUi(<ModelEditor open provider={provider} api={api()} instanceId="ime-id" onOpenChange={vi.fn()} onSaved={vi.fn()} onRemoved={vi.fn()} />)
    const input = screen.getByLabelText('模型标识')
    expect(input).toHaveAttribute('id', 'model-id')
    expect(fireEvent.keyDown(input, { key: 'Enter', isComposing: true })).toBe(false)
    expect(input).toHaveValue('')
  })

  it('closes both layers and notifies the parent after removing an edited model', async () => {
    const onOpenChange = vi.fn()
    const onRemoved = vi.fn()
    const modelApi = api({ removeModel: vi.fn().mockResolvedValue(undefined) })
    const { user } = renderModelUi(<ModelEditor open provider={provider} model={model} api={modelApi} instanceId="delete" onOpenChange={onOpenChange} onSaved={vi.fn()} onRemoved={onRemoved} />)
    await user.click(screen.getByRole('button', { name: '从目录移除' }))
    await user.click(within(screen.getByRole('dialog', { name: '删除模型' })).getByRole('button', { name: '确认移除' }))
    await waitFor(() => expect(modelApi.removeModel).toHaveBeenCalledWith(model.id))
    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(onRemoved).toHaveBeenCalledOnce()
  })

  it.each(['1.5', '9007199254740992'])('rejects invalid context value %s without sending a request', async (context) => {
    const modelApi = api()
    const { user } = renderModelUi(<ModelEditor open provider={provider} api={modelApi} instanceId={`invalid-${context}`} onOpenChange={vi.fn()} onSaved={vi.fn()} onRemoved={vi.fn()} />)
    await user.type(screen.getByLabelText('模型标识'), 'manual'); await user.type(screen.getByLabelText('显示名称'), 'Manual'); await user.type(screen.getByLabelText('上下文窗口'), context)
    await user.click(screen.getByRole('button', { name: '保存模型' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('正安全整数')
    expect(modelApi.createModel).not.toHaveBeenCalled()
  })
})
