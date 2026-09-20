import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value),
    removeItem: (key: string) => data.delete(key),
  })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})

import type { ModuleType } from '../types'
import { ConfigPanel } from '../components/ConfigPanel'
import { useWorkflowStore as store } from '../editor-store'
import { useGlobalConfigStore as config } from '../hooks/stores/globalConfigStore'
import { setStudioTransport } from '../api/transport'
import { mockRequest } from '../api/mock-server'

const initialConfig = structuredClone(config.getState().config)
const originalScroll = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollIntoView')
const primary = { id: 'primary', providerId: 'provider-a', providerName: '主供应商', modelKey: 'model-a', displayName: '主模型', tagsJson: [] }
const secondary = { id: 'secondary', providerId: 'provider-b', providerName: '备用供应商', modelKey: 'model-b', displayName: '备用模型', tagsJson: [] }

beforeEach(() => {
  config.setState({ config: structuredClone(initialConfig) })
  config.getState().updateAIConfig({ autoFallback: false })
  setStudioTransport(async (input) => {
    return String(input).endsWith('/api/v1/models/options')
      ? Response.json({ items: [primary, secondary], total: 2 })
      : mockRequest(input)
  })
  store.getState().clearWorkflow()
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: vi.fn() })
})

afterEach(() => {
  cleanup()
  setStudioTransport(mockRequest)
  config.setState({ config: structuredClone(initialConfig) })
  if (originalScroll) Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', originalScroll)
  else Reflect.deleteProperty(HTMLElement.prototype, 'scrollIntoView')
})

function create(type: ModuleType) {
  store.getState().addNode(type, { x: 120, y: 240 })
  return store.getState().nodes.find(node => node.data.moduleType === type)!.id
}

const data = (id: string) => store.getState().nodes.find(node => node.id === id)!.data
const picker = () => within(screen.getByText('主应用模型').parentElement!).getByRole('combobox')
async function choose(label: string) {
  await waitFor(() => expect(picker().getAttribute('data-disabled')).toBeNull())
  fireEvent.keyDown(picker(), { key: 'ArrowDown' })
  fireEvent.click(await screen.findByRole('option', { name: label }))
}

it.each([
  'ai_chat', 'ai_vision', 'ai_vision_act',
  'ai_extract', 'ai_classify', 'ai_summarize', 'ai_translate',
  'ai_sentiment', 'ai_normalize', 'ai_dedup_semantic', 'ai_route',
] as const)('NODE.%s.model-picker.entry: stores only a managed model id and preserves it on document reopen', async type => {
  const id = create(type)
  store.getState().updateNodeData(id, {
    apiUrl: 'https://legacy.invalid', apiKey: 'legacy-secret', model: 'legacy-model',
    fallbackModels: [{ apiKey: 'fallback-secret' }], temperature: 0, maxTokens: 1234,
  })
  store.getState().addNode(type, { x: 400, y: 240 })
  const other = store.getState().nodes.find(node => node.data.moduleType === type && node.id !== id)!
  const otherBefore = structuredClone(other.data)
  render(<ConfigPanel selectedNodeId={id} />)
  await choose('主模型（主供应商）')
  expect(data(id)).toMatchObject({ modelId: primary.id, temperature: 0, maxTokens: 1234 })
  expect(data(id).apiUrl).toBeUndefined()
  expect(data(id).apiKey).toBeUndefined()
  expect(data(id).model).toBeUndefined()
  expect(data(id).fallbackModels).toBeUndefined()
  expect(data(other.id)).toEqual(otherBefore)
  const content = store.getState().exportWorkflow()
  cleanup()
  act(() => { store.getState().clearWorkflow(); expect(store.getState().importWorkflow(content)).toBe(true) })
  render(<ConfigPanel selectedNodeId={id} />)
  await waitFor(() => expect(picker().textContent).toContain('主模型'))
  expect(content).not.toContain('legacy-secret')
})

it('TOOL.ai-model-picker.empty: reports the missing managed-model dependency without exposing manual secret fields', async () => {
  setStudioTransport(async () => Response.json({ items: [], total: 0 }))
  const id = create('ai_chat')
  render(<ConfigPanel selectedNodeId={id} />)
  expect(await screen.findByText('主应用尚未配置可用模型')).not.toBeNull()
  expect(screen.queryByLabelText('API密钥')).toBeNull()
  expect(data(id).modelId).toBeUndefined()
})

it('TOOL.ai-model-picker.fallback: stores ordered managed fallback ids and never provider secrets', async () => {
  config.getState().updateAIConfig({ autoFallback: true })
  const id = create('ai_chat')
  render(<ConfigPanel selectedNodeId={id} />)
  await choose('主模型（主供应商）')
  await waitFor(() => expect(data(id).fallbackModelIds).toEqual([secondary.id]))
  expect(data(id).fallbackModels).toBeUndefined()
  expect(store.getState().exportWorkflow()).not.toContain('apiKey')
  act(() => config.getState().updateAIConfig({ autoFallback: false }))
  await waitFor(() => expect(data(id).fallbackModelIds).toBeUndefined())
})

it('TOOL.ai-model-picker.removed-model: keeps the stable id and asks the user to reselect', async () => {
  const id = create('ai_chat')
  store.getState().updateNodeData(id, { modelId: 'removed-model' })
  render(<ConfigPanel selectedNodeId={id} />)
  expect(await screen.findByText('已选模型不可用，请从主应用模型中重新选择')).not.toBeNull()
  expect(data(id).modelId).toBe('removed-model')
})

it('TOOL.ai-model-picker.failure: preserves node data and shows the service error', async () => {
  setStudioTransport(async () => Response.json({ detail: 'fixture unavailable' }, { status: 503 }))
  const id = create('ai_chat')
  store.getState().updateNodeData(id, { modelId: primary.id })
  render(<ConfigPanel selectedNodeId={id} />)
  expect(await screen.findByText(/模型列表加载失败/)).not.toBeNull()
  expect(data(id).modelId).toBe(primary.id)
})

it.each(['ai_chat', 'ai_extract', 'ai_classify', 'ai_summarize', 'ai_translate', 'ai_sentiment', 'ai_normalize', 'ai_dedup_semantic', 'ai_route'] as const)(
  'NODE.%s.defaults: does not copy local provider credentials into new workflow documents', type => {
    config.getState().updateAIConfig({ apiUrl: 'https://legacy.invalid', apiKey: 'legacy-secret', model: 'legacy-model' })
    const id = create(type)
    expect(data(id).apiUrl).toBeUndefined()
    expect(data(id).apiKey).toBeUndefined()
    expect(data(id).model).toBeUndefined()
  },
)
