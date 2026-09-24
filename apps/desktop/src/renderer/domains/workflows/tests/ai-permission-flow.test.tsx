import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value),
    removeItem: (key: string) => data.delete(key),
  })
})

import { acknowledgeAssistantMcpTool, executeClientAction } from '../api/aiAssistantSkills'
import { socketService } from '../events'
import { AIAssistantPanel } from '../components/assistant/AIAssistantPanel'
import { useWorkflowStore } from '../editor-store'
import { useAIAssistantStore } from '../hooks/stores/aiAssistantStore'
import { cancelPendingApproval, useAIPermissionStore } from '../hooks/stores/aiPermissionStore'
import { useGlobalConfigStore } from '../hooks/stores/globalConfigStore'

const originalConfig = structuredClone(useGlobalConfigStore.getState().config)

beforeEach(() => {
  cancelPendingApproval()
  useWorkflowStore.getState().clearWorkflow()
  useGlobalConfigStore.setState({ config: structuredClone(originalConfig) })
  useGlobalConfigStore.getState().updateAIAssistantConfig({
    enableTools: true,
    autoApprove: false,
    permissionMode: 'smart',
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
})

afterEach(() => {
  cleanup()
  cancelPendingApproval()
  useWorkflowStore.getState().clearWorkflow()
  useGlobalConfigStore.setState({ config: structuredClone(originalConfig) })
})

function addNode() {
  return executeClientAction('add_nodes', {
    nodes: [{ id: 'assistant-node', type: 'open_page', data: { url: 'https://example.test' } }],
  })
}

async function beginApproval() {
  let result!: ReturnType<typeof addNode>
  await act(async () => {
    result = addNode()
    await Promise.resolve()
  })
  await screen.findByText('小助手请求授权：添加节点')
  return { result }
}

it('F5.AI.permission.approve: applies the exact pending action only after the visible approval button', async () => {
  useGlobalConfigStore.getState().updateAIAssistantConfig({ permissionMode: 'approval' })
  render(<AIAssistantPanel />)
  const { result } = await beginApproval()
  expect(useWorkflowStore.getState().nodes).toEqual([])
  fireEvent.click(screen.getByRole('button', { name: '允许执行' }))
  await expect(result).resolves.toMatchObject({ success: true })
  expect(useWorkflowStore.getState().nodes.map(node => node.id)).toEqual(['assistant-node'])
  expect(screen.queryByText('小助手请求授权：添加节点')).toBeNull()
})

it('F5.AI.permission.reject: reports rejection without mutating the draft or stopping later requests', async () => {
  useGlobalConfigStore.getState().updateAIAssistantConfig({ permissionMode: 'approval' })
  render(<AIAssistantPanel />)
  const { result: rejected } = await beginApproval()
  fireEvent.click(screen.getByRole('button', { name: '拒绝（继续任务）' }))
  await expect(rejected).resolves.toMatchObject({ success: false, error: expect.stringContaining('继续') })
  expect(useWorkflowStore.getState().nodes).toEqual([])

  const { result: next } = await beginApproval()
  fireEvent.click(screen.getByRole('button', { name: '允许执行' }))
  await expect(next).resolves.toMatchObject({ success: true })
})

it('F5.AI.permission.modes: smart gates high-risk actions while full and auto-approve bypass the prompt', async () => {
  useWorkflowStore.getState().addNode('open_page', { x: 0, y: 0 })
  const nodeId = useWorkflowStore.getState().nodes[0].id
  render(<AIAssistantPanel />)

  const lowRisk = await addNode()
  expect(lowRisk.success).toBe(true)
  expect(screen.queryByText(/小助手请求授权/)).toBeNull()

  let deletion!: ReturnType<typeof executeClientAction>
  await act(async () => {
    deletion = executeClientAction('delete_node', { node_id: nodeId })
    await Promise.resolve()
  })
  await screen.findByText('小助手请求授权：删除节点')
  fireEvent.click(screen.getByRole('button', { name: '允许执行' }))
  await expect(deletion).resolves.toMatchObject({ success: true })

  useGlobalConfigStore.getState().updateAIAssistantConfig({ permissionMode: 'full' })
  expect((await executeClientAction('delete_node', { node_id: 'assistant-node' })).success).toBe(true)
  expect(screen.queryByText(/小助手请求授权/)).toBeNull()

  useWorkflowStore.getState().addNode('open_page', { x: 0, y: 0 })
  const autoId = useWorkflowStore.getState().nodes[0].id
  useGlobalConfigStore.getState().updateAIAssistantConfig({ permissionMode: 'approval', autoApprove: true })
  expect((await executeClientAction('delete_node', { node_id: autoId })).success).toBe(true)
  expect(screen.queryByText(/小助手请求授权/)).toBeNull()
})

it('F5.AI.permission.disabled: rejects client actions before changing the document', async () => {
  useGlobalConfigStore.getState().updateAIAssistantConfig({ enableTools: false, permissionMode: 'full' })
  render(<AIAssistantPanel />)
  await expect(addNode()).resolves.toMatchObject({ success: false, error: expect.stringContaining('工具调用已关闭') })
  expect(useWorkflowStore.getState().nodes).toEqual([])
  expect(useAIPermissionStore.getState().pending).toBeNull()
})

it('F5.AI.permission.cancel: closing or unmounting the panel releases the pending action as rejected', async () => {
  useGlobalConfigStore.getState().updateAIAssistantConfig({ permissionMode: 'approval' })
  const view = render(<AIAssistantPanel />)
  const { result: closed } = await beginApproval()
  fireEvent.click(screen.getByRole('button', { name: '关闭小助手' }))
  await expect(closed).resolves.toMatchObject({ success: false })
  expect(useWorkflowStore.getState().nodes).toEqual([])

  act(() => useAIAssistantStore.getState().setPanelOpen(true))
  const { result: unmounted } = await beginApproval()
  view.unmount()
  await expect(unmounted).resolves.toMatchObject({ success: false })
  expect(useAIPermissionStore.getState().pending).toBeNull()
})

it('F5.AI.permission.concurrent: a second action cannot replace or strand the visible approval', async () => {
  useGlobalConfigStore.getState().updateAIAssistantConfig({ permissionMode: 'approval' })
  render(<AIAssistantPanel />)
  const { result: first } = await beginApproval()
  await expect(addNode()).resolves.toMatchObject({ success: false, error: expect.stringContaining('拒绝') })
  expect(screen.getAllByText('小助手请求授权：添加节点')).toHaveLength(1)
  fireEvent.click(screen.getByRole('button', { name: '允许执行' }))
  await expect(first).resolves.toMatchObject({ success: true })
  await waitFor(() => expect(useAIPermissionStore.getState().pending).toBeNull())
})

it('F5.AI.permission.mcp: requires visible approval even when global and server auto approval are enabled', async () => {
  useGlobalConfigStore.getState().updateAIAssistantConfig({ permissionMode: 'full', autoApprove: true })
  const calls: string[] = []
  vi.spyOn(socketService, 'command').mockImplementation(async (event, _data, commandId) => {
    calls.push(event)
    return { commandId, success: true, httpStatus: 200 } as never
  })
  render(<AIAssistantPanel />)
  let result!: ReturnType<typeof acknowledgeAssistantMcpTool>
  await act(async () => {
    result = acknowledgeAssistantMcpTool({
      session_id: 'mcp-session',
      tool_call_id: 'mcp-tool',
      action: 'mcp__fixture__echo',
      payload: { text: 'hello' },
    })
    await Promise.resolve()
  })
  await screen.findByText('小助手请求授权：MCP 工具：fixture / echo')
  expect(calls).toEqual(['ai_client_action_claim'])
  fireEvent.click(screen.getByRole('button', { name: '允许执行' }))
  await expect(result).resolves.toMatchObject({ success: true })
  expect(calls).toEqual(['ai_client_action_claim', 'ai_client_action_ack'])
})
