import { afterEach, expect, it } from 'vitest'

import { aiAssistantApi } from '../api/aiAssistantApi'
import { setStudioTransport } from '../api/transport'
import { mockRequest } from '../api/mock-server'

afterEach(() => setStudioTransport(mockRequest))

it('F5.AI.model-boundary: sends stable main-app model ids and never provider secrets', async () => {
  let body: Record<string, unknown> | undefined
  setStudioTransport(async (input, init) => {
    if (String(input).endsWith('/api/ai-assistant/chat')) {
      body = JSON.parse(String(init?.body))
      return Response.json({
        sessionId: 'assistant-session',
        message: { id: 'reply', role: 'assistant', content: '完成' },
      })
    }
    return mockRequest(input, init)
  })

  const response = await aiAssistantApi.chat({
    sessionId: 'assistant-session',
    message: '添加节点',
    config: {
      modelId: 'managed-primary',
      temperature: 0.2,
      maxTokens: 1024,
      systemPrompt: '',
      enableTools: true,
      autoApprove: false,
    },
    workflowContext: { revision: 3 },
    fallbackModelIds: ['managed-fallback'],
  })

  expect(response.success).toBe(true)
  expect(body).toEqual(expect.objectContaining({
    sessionId: 'assistant-session',
    config: expect.objectContaining({ modelId: 'managed-primary' }),
    fallbackModelIds: ['managed-fallback'],
  }))
  expect(JSON.stringify(body)).not.toMatch(/api[_A-Z]?key|api[_A-Z]?url/i)
})

it('F5.AI.pending-restore: exposes the pending action needed after reconnect', async () => {
  setStudioTransport(async () => Response.json({
    id: 'assistant-session',
    title: '恢复',
    messages: [],
    status: 'waiting_for_action',
    pendingAction: { commandId: 'tool-1', action: 'add_nodes', payload: { nodes: [] } },
    revision: 4,
  }))

  const response = await aiAssistantApi.getSession('assistant-session')

  expect(response.data?.pendingAction).toEqual({
    commandId: 'tool-1', action: 'add_nodes', payload: { nodes: [] },
  })
})
