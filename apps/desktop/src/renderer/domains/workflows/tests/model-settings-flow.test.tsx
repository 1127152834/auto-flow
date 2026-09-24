import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value),
    removeItem: (key: string) => data.delete(key),
  })
})

import { configureStudioConnection } from '../api/config'
import { mockRequest } from '../api/mock-server'
import { GlobalConfigDialog } from '../components/GlobalConfigDialog'
import { useGlobalConfigStore } from '../hooks/stores/globalConfigStore'

const originalConfig = structuredClone(useGlobalConfigStore.getState().config)
const mainModel = { id: 'assistant-main', providerId: 'provider', providerName: '主供应商', modelKey: 'model-a', displayName: '主模型', tagsJson: ['chat', 'vision'] }
let restoreConnection: () => void
const originalScroll = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollIntoView')

beforeEach(() => {
  useGlobalConfigStore.setState({ config: structuredClone(originalConfig) })
  useGlobalConfigStore.getState().updateAIConfig({ models: [], activeModelId: undefined, autoFallback: false })
  useGlobalConfigStore.getState().updateAIAssistantConfig({ modelId: undefined, fallbackModelIds: undefined, autoFallback: false, autoSceneRoute: false })
  restoreConnection = configureStudioConnection('http://autoflow-studio.mock', async (input, init) => {
    if (String(input).endsWith('/api/v1/models/options')) return Response.json({ items: [mainModel], total: 1 })
    if (String(input).endsWith('/api/ai-assistant/test-connection')) {
      expect(JSON.parse(String(init?.body))).toEqual({ modelId: mainModel.id })
      return Response.json({ success: true, message: 'Mock 连接可用', detail: 'OK', latencyMs: 2 })
    }
    return mockRequest(input, init)
  })
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: vi.fn() })
})

afterEach(() => {
  cleanup()
  restoreConnection()
  useGlobalConfigStore.setState({ config: structuredClone(originalConfig) })
  if (originalScroll) Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', originalScroll)
  else Reflect.deleteProperty(HTMLElement.prototype, 'scrollIntoView')
})

function openSettings() {
  return render(<GlobalConfigDialog isOpen onClose={vi.fn()} />)
}

it('F5.MODEL.dialog-profiles: creates, selects, edits and removes AI module profiles through the settings UI', () => {
  const view = openSettings()
  fireEvent.click(screen.getByRole('button', { name: 'AI对话' }))
  fireEvent.change(screen.getByDisplayValue(String(originalConfig.ai.temperature)), { target: { value: '0' } })
  expect(useGlobalConfigStore.getState().config.ai.temperature).toBe(0)

  fireEvent.click(screen.getByRole('button', { name: '添加模型' }))
  fireEvent.change(screen.getByPlaceholderText('显示名（如 GPT-4o / DeepSeek）'), { target: { value: '主模型' } })
  fireEvent.change(screen.getByPlaceholderText('API 地址 https://api.openai.com/v1'), { target: { value: 'https://model.test/v1' } })
  fireEvent.change(screen.getByPlaceholderText('API 密钥 sk-xxx'), { target: { value: 'fixture-key' } })
  fireEvent.change(screen.getByPlaceholderText('模型名 gpt-4o-mini'), { target: { value: 'fixture-model' } })
  fireEvent.click(screen.getByRole('switch', { name: '失败自动切换' }))

  const saved = useGlobalConfigStore.getState().config.ai
  expect(saved.models).toEqual([expect.objectContaining({ label: '主模型', apiUrl: 'https://model.test/v1', apiKey: 'fixture-key', model: 'fixture-model' })])
  expect(saved.activeModelId).toBe(saved.models![0].id)
  expect(saved.autoFallback).toBe(true)

  view.unmount()
  openSettings()
  fireEvent.click(screen.getByRole('button', { name: 'AI对话' }))
  expect(screen.getByDisplayValue('主模型')).toBeTruthy()
  fireEvent.click(screen.getByTitle('删除'))
  expect(useGlobalConfigStore.getState().config.ai.models).toEqual([])
  expect(useGlobalConfigStore.getState().config.ai.activeModelId).toBeUndefined()
})

it('F5.MODEL.assistant-managed: persists the managed model, routing and permissions without secrets', async () => {
  openSettings()
  fireEvent.click(screen.getByRole('button', { name: '小助手' }))
  const model = await screen.findByRole('combobox', { name: '小助手主应用模型' })
  fireEvent.keyDown(model, { key: 'ArrowDown' })
  fireEvent.click(await screen.findByRole('option', { name: '主模型（主供应商）' }))
  fireEvent.change(screen.getByDisplayValue(String(originalConfig.aiAssistant.temperature)), { target: { value: '0' } })
  fireEvent.click(screen.getByRole('button', { name: /^逐项确认/ }))
  fireEvent.click(screen.getByRole('switch', { name: '失败自动切换' }))
  fireEvent.click(screen.getByRole('switch', { name: '场景自动选模型' }))

  const saved = useGlobalConfigStore.getState().config.aiAssistant
  expect(saved).toMatchObject({ modelId: mainModel.id, temperature: 0, permissionMode: 'approval', autoFallback: true, autoSceneRoute: true })
  expect(JSON.stringify(saved)).not.toContain('apiKey')
})

it('F5.MODEL.connection-test: tests the selected managed model and consumes explicit failure responses', async () => {
  openSettings()
  fireEvent.click(screen.getByRole('button', { name: '小助手' }))
  const model = await screen.findByRole('combobox', { name: '小助手主应用模型' })
  fireEvent.keyDown(model, { key: 'ArrowDown' })
  fireEvent.click(await screen.findByRole('option', { name: '主模型（主供应商）' }))
  fireEvent.click(screen.getByRole('button', { name: '测试连接' }))
  await screen.findByText(/Mock 连接可用（2ms）/)

  restoreConnection()
  restoreConnection = configureStudioConnection('http://model-settings.test', async (input, init) => {
    if (String(input).includes('/ai-assistant/test-connection')) {
      expect(JSON.parse(String(init?.body))).toEqual({ modelId: mainModel.id })
      return Response.json({ success: false, error: '模型服务拒绝连接' }, { status: 503 })
    }
    if (String(input).endsWith('/api/v1/models/options')) return Response.json({ items: [mainModel], total: 1 })
    return mockRequest(input, init)
  })
  fireEvent.click(screen.getByRole('button', { name: '测试连接' }))
  await waitFor(() => expect(screen.getByText(/模型服务拒绝连接/)).toBeTruthy())
})
