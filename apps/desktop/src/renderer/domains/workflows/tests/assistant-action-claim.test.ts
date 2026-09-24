import { beforeEach, expect, it, vi } from 'vitest'

vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value),
    removeItem: (key: string) => data.delete(key),
  })
})

import { acknowledgeAssistantClientAction } from '../api/aiAssistantSkills'
import { socketService } from '../events'
import { useWorkflowStore } from '../editor-store'
import { useGlobalConfigStore } from '../hooks/stores/globalConfigStore'

beforeEach(() => {
  vi.restoreAllMocks()
  useWorkflowStore.getState().clearWorkflow()
  useGlobalConfigStore.getState().updateAIAssistantConfig({
    enableTools: true,
    autoApprove: true,
    permissionMode: 'full',
  })
})

it('F5.AI.action-claim: claims once before mutating and replays only the stored result', async () => {
  const calls: Array<{ event: string; data: Record<string, unknown>; commandId: string }> = []
  vi.spyOn(socketService, 'command').mockImplementation(async (event, data, commandId) => {
    calls.push({ event, data: data as Record<string, unknown>, commandId })
    return { commandId, success: true, httpStatus: 200 } as never
  })
  const request = {
    session_id: 'assistant-session',
    tool_call_id: 'tool-once',
    action: 'add_nodes',
    payload: { nodes: [{ id: 'assistant-node', type: 'open_page' }] },
  }

  await acknowledgeAssistantClientAction(request)
  await acknowledgeAssistantClientAction(request)

  expect(useWorkflowStore.getState().nodes.map(node => node.id)).toEqual(['assistant-node'])
  expect(calls.map(call => call.event)).toEqual([
    'ai_client_action_claim',
    'ai_client_action_ack',
  ])
  expect(calls[0].data).toMatchObject({
    session_id: 'assistant-session',
    tool_call_id: 'tool-once',
    executor_id: expect.any(String),
  })
  expect(calls[1].data).toMatchObject({
    session_id: 'assistant-session',
    tool_call_id: 'tool-once',
    claim_command_id: calls[0].commandId,
    result: { success: true },
  })
  expect(calls[0].commandId).not.toBe(calls[1].commandId)
})

it('F5.AI.action-claim-conflict: never mutates when another renderer already owns the action', async () => {
  vi.spyOn(socketService, 'command').mockImplementation(async (_event, _data, commandId) => ({
    commandId,
    success: false,
    httpStatus: 409,
    error: '工具请求已由其他窗口认领，结果尚未确认',
  } as never))

  const receipt = await acknowledgeAssistantClientAction({
    session_id: 'other-session',
    tool_call_id: 'other-tool',
    action: 'add_nodes',
    payload: { nodes: [{ id: 'must-not-exist', type: 'open_page' }] },
  })

  expect(receipt).toMatchObject({ success: false, httpStatus: 409 })
  expect(useWorkflowStore.getState().nodes).toEqual([])
})
