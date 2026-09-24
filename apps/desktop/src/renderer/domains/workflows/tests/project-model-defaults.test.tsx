import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value),
    removeItem: (key: string) => data.delete(key),
  })
})

import { modelApi } from '../api'
import { aiAssistantApi } from '../api/aiAssistantApi'
import { configureStudioConnection } from '../api/config'
import { AIAssistantPanel } from '../components/assistant/AIAssistantPanel'
import { AIModelPicker } from '../components/config-panels/AIModuleConfigs'
import type { NodeData } from '../editor-store'
import { useAIAssistantStore } from '../hooks/stores/aiAssistantStore'
import { useGlobalConfigStore } from '../hooks/stores/globalConfigStore'

const primary = { id: 'model-primary', providerId: 'provider-a', providerName: '主供应商', modelKey: 'model-a', displayName: '主模型', tagsJson: ['chat'] }
const secondary = { id: 'model-secondary', providerId: 'provider-b', providerName: '项目供应商', modelKey: 'model-b', displayName: '项目默认模型', tagsJson: ['chat'] }
const modelOptions = { items: [primary, secondary], total: 2 }
const originalConfig = structuredClone(useGlobalConfigStore.getState().config)
const originalScroll = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollIntoView')

let restoreConnection: (() => void) | undefined

beforeEach(() => {
  window.history.replaceState({}, '', '/studio.html')
  restoreConnection = configureStudioConnection('http://project-model.test', async () => Response.json({ code: 'NOT_FOUND' }, { status: 404 }))
  useGlobalConfigStore.setState({
    config: structuredClone(originalConfig),
    projectResources: { scope: null },
  })
  useGlobalConfigStore.getState().updateAIAssistantConfig({
    modelId: undefined,
    autoFallback: false,
    autoSceneRoute: false,
  })
  useAIAssistantStore.setState({
    isPanelOpen: true,
    currentSessionId: null,
    messages: [],
    isSending: false,
    liveToolCalls: [],
    sessions: [],
    rollbackSnapshots: {},
  })
  vi.spyOn(modelApi, 'listOptions').mockResolvedValue({ success: true, data: modelOptions })
  vi.spyOn(modelApi, 'projectDefault').mockResolvedValue({ success: true, data: null })
  vi.spyOn(aiAssistantApi, 'listSessions').mockResolvedValue({ success: true, data: [] })
  vi.spyOn(aiAssistantApi, 'chat').mockResolvedValue({ success: false, error: 'fixture stopped after request capture' })
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: vi.fn() })
  HTMLElement.prototype.hasPointerCapture = vi.fn(() => false)
  HTMLElement.prototype.setPointerCapture = vi.fn()
  HTMLElement.prototype.releasePointerCapture = vi.fn()
})

afterEach(() => {
  cleanup()
  restoreConnection?.()
  restoreConnection = undefined
  vi.restoreAllMocks()
  window.history.replaceState({}, '', '/studio.html')
  useGlobalConfigStore.setState({
    config: structuredClone(originalConfig),
    projectResources: { scope: null },
  })
  if (originalScroll) Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', originalScroll)
  else Reflect.deleteProperty(HTMLElement.prototype, 'scrollIntoView')
})

function enterProject(projectId = 'project-a') {
  window.history.replaceState({}, '', `/studio.html?workspaceKey=workspace-a&projectId=${projectId}`)
}

function picker() {
  return within(screen.getByText('主应用模型').parentElement!).getByRole('combobox')
}

function nodeData(overrides: Partial<NodeData> = {}): NodeData {
  return { label: 'AI 对话', moduleType: 'ai_chat', ...overrides }
}

async function choosePickerModel(label: string) {
  fireEvent.keyDown(picker(), { key: 'ArrowDown' })
  fireEvent.click(await screen.findByRole('option', { name: label }))
}

async function sendAssistantMessage(message = '检查项目默认模型') {
  const input = await screen.findByPlaceholderText(/告诉我你想做什么/)
  fireEvent.change(input, { target: { value: message } })
  fireEvent.click(screen.getByRole('button', { name: '发送消息' }))
}

describe('Studio project model defaults', () => {
  it('shows inheritance at the empty node value without writing the project default into the workflow document', async () => {
    enterProject()
    vi.mocked(modelApi.projectDefault).mockResolvedValue({ success: true, data: { modelId: secondary.id } })
    const onBatchChange = vi.fn()

    render(<AIModelPicker data={nodeData()} onBatchChange={onBatchChange} />)

    await waitFor(() => expect(picker().textContent).toContain('继承项目默认：项目默认模型（项目供应商）'))
    expect(onBatchChange).not.toHaveBeenCalled()
    await choosePickerModel('主模型（主供应商）')
    expect(onBatchChange).toHaveBeenCalledWith(expect.objectContaining({ modelId: primary.id }))
  })

  it('keeps an explicit node model usable when the project default is missing', async () => {
    enterProject()
    vi.mocked(modelApi.projectDefault).mockResolvedValue({ success: false, error: '项目未设置默认模型服务', httpStatus: 422 })
    const onBatchChange = vi.fn()

    render(<AIModelPicker data={nodeData({ modelId: primary.id })} onBatchChange={onBatchChange} />)

    await waitFor(() => expect(picker().textContent).toContain('主模型'))
    expect(picker().getAttribute('data-disabled')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(onBatchChange).not.toHaveBeenCalled()
  })

  it('reports an unavailable inherited default without choosing the first model', async () => {
    enterProject()
    vi.mocked(modelApi.projectDefault).mockResolvedValue({ success: false, error: '项目默认模型服务没有可用模型', httpStatus: 409 })
    const onBatchChange = vi.fn()

    render(<AIModelPicker data={nodeData()} onBatchChange={onBatchChange} />)

    expect((await screen.findByRole('alert')).textContent).toContain('项目默认模型服务没有可用模型')
    expect(picker().textContent).not.toContain('主模型（主供应商）')
    expect(onBatchChange).not.toHaveBeenCalled()
  })

  it('derives fallback models from an inherited project default without writing modelId', async () => {
    enterProject()
    useGlobalConfigStore.getState().updateAIConfig({ autoFallback: true })
    vi.mocked(modelApi.projectDefault).mockResolvedValue({ success: true, data: { modelId: secondary.id } })
    const onBatchChange = vi.fn()

    render(<AIModelPicker data={nodeData()} onBatchChange={onBatchChange} />)

    await waitFor(() => expect(onBatchChange).toHaveBeenCalledWith({ fallbackModelIds: [primary.id] }))
    expect(onBatchChange.mock.calls.some(([change]) => Object.prototype.hasOwnProperty.call(change, 'modelId'))).toBe(false)
  })

  it('does not clear saved fallback models when the explicit model no longer exists', async () => {
    enterProject()
    const onBatchChange = vi.fn()

    render(
      <AIModelPicker
        data={nodeData({ modelId: 'removed-model', fallbackModelIds: [secondary.id] })}
        onBatchChange={onBatchChange}
      />,
    )

    expect(await screen.findByText('已选模型不可用，请从主应用模型中重新选择')).toBeTruthy()
    expect(onBatchChange).not.toHaveBeenCalled()
  })

  it('does not clear saved fallback models when the managed-model list fails to load', async () => {
    enterProject()
    vi.mocked(modelApi.listOptions).mockResolvedValue({ success: false, error: '模型列表暂时不可用', httpStatus: 503 })
    const onBatchChange = vi.fn()

    render(
      <AIModelPicker
        data={nodeData({ modelId: primary.id, fallbackModelIds: [secondary.id] })}
        onBatchChange={onBatchChange}
      />,
    )

    expect((await screen.findByRole('alert')).textContent).toContain('模型列表暂时不可用')
    expect(onBatchChange).not.toHaveBeenCalled()
  })

  it('sends with the project default without mutating the standalone assistant model', async () => {
    useGlobalConfigStore.getState().updateAIAssistantConfig({ modelId: primary.id })
    enterProject()
    vi.mocked(modelApi.projectDefault).mockResolvedValue({ success: true, data: { modelId: secondary.id } })

    render(<AIAssistantPanel />)

    await waitFor(() => expect(screen.getByTitle('切换模型').textContent).toContain('项目默认模型'))
    await sendAssistantMessage()
    await waitFor(() => expect(aiAssistantApi.chat).toHaveBeenCalledTimes(1))
    expect(vi.mocked(aiAssistantApi.chat).mock.calls[0][0].config.modelId).toBe(secondary.id)
    expect(useGlobalConfigStore.getState().config.aiAssistant.modelId).toBe(primary.id)
    expect(useGlobalConfigStore.getState().projectResources.modelId).toBeUndefined()
  })

  it('stores an explicit assistant override in the project scope and sends with it', async () => {
    useGlobalConfigStore.getState().updateAIAssistantConfig({ modelId: secondary.id })
    enterProject()
    vi.mocked(modelApi.projectDefault).mockResolvedValue({ success: true, data: { modelId: secondary.id } })
    render(<AIAssistantPanel />)
    await waitFor(() => expect(screen.getByTitle('切换模型').textContent).toContain('项目默认模型'))

    fireEvent.click(screen.getByTitle('切换模型'))
    fireEvent.click(screen.getByRole('button', { name: /主模型.*主供应商/ }))
    expect(useGlobalConfigStore.getState().projectResources.modelId).toBe(primary.id)
    expect(useGlobalConfigStore.getState().config.aiAssistant.modelId).toBe(secondary.id)

    await sendAssistantMessage('使用项目覆盖')
    await waitFor(() => expect(aiAssistantApi.chat).toHaveBeenCalledTimes(1))
    expect(vi.mocked(aiAssistantApi.chat).mock.calls[0][0].config.modelId).toBe(primary.id)
  })

  it('keeps an explicit project assistant override usable when the project default is unavailable', async () => {
    enterProject()
    useGlobalConfigStore.getState().syncProjectResourceScope()
    useGlobalConfigStore.getState().setAssistantModelId(primary.id)
    vi.mocked(modelApi.projectDefault).mockResolvedValue({ success: false, error: '项目默认模型服务不可用', httpStatus: 409 })

    render(<AIAssistantPanel />)

    await waitFor(() => expect(screen.getByTitle('切换模型').textContent).toContain('主模型'))
    await sendAssistantMessage('使用项目显式覆盖')
    await waitFor(() => expect(aiAssistantApi.chat).toHaveBeenCalledTimes(1))
    expect(vi.mocked(aiAssistantApi.chat).mock.calls[0][0].config.modelId).toBe(primary.id)
    expect(screen.queryByText('项目默认模型服务不可用')).toBeNull()
  })

  it('blocks the project assistant and explains an unavailable inherited default', async () => {
    enterProject()
    vi.mocked(modelApi.projectDefault).mockResolvedValue({ success: false, error: '项目未设置默认模型服务', httpStatus: 422 })

    render(<AIAssistantPanel />)

    expect(await screen.findByText('项目未设置默认模型服务')).toBeTruthy()
    expect((screen.getByRole('button', { name: '发送消息' }) as HTMLButtonElement).disabled).toBe(true)
    expect(aiAssistantApi.chat).not.toHaveBeenCalled()
    expect(useGlobalConfigStore.getState().config.aiAssistant.modelId).toBeUndefined()
  })

  it('blocks stale sends while model options are reconnecting and keeps project overrides out of another project', async () => {
    enterProject('project-a')
    vi.mocked(modelApi.projectDefault).mockResolvedValue({ success: true, data: { modelId: secondary.id } })
    render(<AIAssistantPanel />)
    await waitFor(() => expect(screen.getByTitle('切换模型').textContent).toContain('项目默认模型'))
    act(() => useGlobalConfigStore.getState().setAssistantModelId(primary.id))
    await waitFor(() => expect(screen.getByTitle('切换模型').textContent).toContain('主模型'))

    window.history.replaceState({}, '', '/studio.html?workspaceKey=workspace-a&projectId=project-b')
    vi.mocked(modelApi.listOptions).mockResolvedValueOnce({ success: false, error: '重连中，模型列表不可用' })
    act(() => window.dispatchEvent(new Event('studio:transport-changed')))

    await screen.findByPlaceholderText('请先在全局配置中配置模型')
    expect(useGlobalConfigStore.getState().projectResources.modelId).toBeUndefined()
    expect((screen.getByRole('button', { name: '发送消息' }) as HTMLButtonElement).disabled).toBe(true)
    expect(aiAssistantApi.chat).not.toHaveBeenCalled()
  })

  it('keeps the standalone first-model initialization behavior', async () => {
    render(<AIAssistantPanel standalone />)

    await waitFor(() => expect(useGlobalConfigStore.getState().config.aiAssistant.modelId).toBe(primary.id))
    expect(screen.getByTitle('切换模型').textContent).toContain('主模型')
    expect(modelApi.projectDefault).not.toHaveBeenCalled()
  })
})
