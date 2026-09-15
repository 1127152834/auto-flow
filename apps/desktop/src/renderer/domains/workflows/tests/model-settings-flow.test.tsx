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
let restoreConnection: () => void

beforeEach(() => {
  useGlobalConfigStore.setState({ config: structuredClone(originalConfig) })
  useGlobalConfigStore.getState().updateAIConfig({ models: [], activeModelId: undefined, autoFallback: false })
  useGlobalConfigStore.getState().updateAIAssistantConfig({ models: [], activeModelId: undefined, autoFallback: false, autoSceneRoute: false })
  restoreConnection = configureStudioConnection('http://autoflow-studio.mock', mockRequest)
})

afterEach(() => {
  cleanup()
  restoreConnection()
  useGlobalConfigStore.setState({ config: structuredClone(originalConfig) })
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

it('F5.MODEL.assistant-profiles: persists scene routing, permissions and model capabilities', () => {
  openSettings()
  fireEvent.click(screen.getByRole('button', { name: '小助手' }))
  fireEvent.change(screen.getByDisplayValue(String(originalConfig.aiAssistant.temperature)), { target: { value: '0' } })
  fireEvent.click(screen.getByRole('button', { name: /^逐项确认/ }))
  fireEvent.click(screen.getByRole('switch', { name: '多模态（视觉）模型' }))
  fireEvent.click(screen.getByRole('switch', { name: '深度思考（推理）模型' }))
  fireEvent.click(screen.getByRole('button', { name: '添加模型' }))
  fireEvent.change(screen.getByPlaceholderText('显示名（如 GPT-4o / DeepSeek）'), { target: { value: '视觉模型' } })
  fireEvent.click(screen.getByRole('checkbox', { name: '多模态' }))
  fireEvent.click(screen.getByRole('switch', { name: '失败自动切换' }))
  fireEvent.click(screen.getByRole('switch', { name: '场景自动选模型' }))

  const saved = useGlobalConfigStore.getState().config.aiAssistant
  expect(saved).toMatchObject({ temperature: 0, permissionMode: 'approval', supportsVision: true, isThinking: true, autoFallback: true, autoSceneRoute: true })
  expect(saved.models).toEqual([expect.objectContaining({ label: '视觉模型', scenes: expect.arrayContaining(['chat', 'vision']) })])
})

it('F5.MODEL.connection-test: validates missing settings and consumes explicit success and failure responses', async () => {
  openSettings()
  fireEvent.click(screen.getByRole('button', { name: '小助手' }))
  const apiAddress = screen.getByPlaceholderText('https://api.openai.com/v1/chat/completions')
  const model = screen.getByPlaceholderText('gpt-4o-mini / glm-4-plus / deepseek-chat')
  fireEvent.change(apiAddress, { target: { value: '' } })
  fireEvent.change(model, { target: { value: '' } })
  fireEvent.click(screen.getByRole('button', { name: '测试连接' }))
  expect(screen.getByText('请先填写 API 地址和模型名称')).toBeTruthy()

  fireEvent.change(apiAddress, { target: { value: 'https://assistant.test/v1' } })
  fireEvent.change(model, { target: { value: 'assistant-model' } })
  fireEvent.click(screen.getByRole('button', { name: '测试连接' }))
  await screen.findByText(/Mock 连接可用/)

  restoreConnection()
  restoreConnection = configureStudioConnection('http://model-settings.test', async (input, init) => {
    if (String(input).includes('/ai-assistant/test-connection')) {
      expect(JSON.parse(String(init?.body))).toMatchObject({
        config: {
          api_url: 'https://assistant.test/v1',
          model: 'assistant-model',
          enable_tools: false,
        },
      })
      return Response.json({ success: false, error: '模型服务拒绝连接' }, { status: 503 })
    }
    return mockRequest(input, init)
  })
  fireEvent.click(screen.getByRole('button', { name: '测试连接' }))
  await waitFor(() => expect(screen.getByText(/模型服务拒绝连接/)).toBeTruthy())
})
