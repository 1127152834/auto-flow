// Source: WebRPA@5ccb900e, services/aiAssistantApi.ts; see SOURCE.md for license and adaptation boundaries.
import { apiRequest } from '../api'
import type { ChatMessage, SessionListItem } from '../hooks/stores/aiAssistantStore'

export interface AssistantConfigPayload {
  modelId: string
  temperature: number
  maxTokens: number
  systemPrompt: string
  enableTools: boolean
  autoApprove: boolean
}

export interface ChatRequestPayload {
  sessionId?: string | null
  message: string
  config: AssistantConfigPayload
  workflowContext?: Record<string, any>
  images?: string[]
  fallbackModelIds?: string[]
}

export interface ChatResponsePayload {
  sessionId: string
  message: ChatMessage
}

export interface AssistantPendingAction {
  commandId: string
  action: string
  payload: Record<string, unknown>
}

export interface AssistantSessionPayload {
  id: string
  title: string
  messages: ChatMessage[]
  status: 'idle' | 'running' | 'waiting_for_action' | 'completed' | 'failed' | 'cancelled'
  pendingAction: AssistantPendingAction | null
  revision: number
}

export const aiAssistantApi = {
  listSessions: () =>
    apiRequest<SessionListItem[]>('/ai-assistant/sessions'),

  createSession: (title?: string) =>
    apiRequest<{ sessionId: string; title: string }>('/ai-assistant/sessions', {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),

  getSession: (id: string) =>
    apiRequest<AssistantSessionPayload>(
      `/ai-assistant/sessions/${id}`
    ),

  deleteSession: (id: string) =>
    apiRequest<{ success: boolean }>(`/ai-assistant/sessions/${id}`, {
      method: 'DELETE',
    }),

  renameSession: (id: string, title: string) =>
    apiRequest<{ success: boolean }>(`/ai-assistant/sessions/${id}/title`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    }),

  /** 消息回滚：把会话截断到指定消息之前（删除该消息及其之后的所有消息） */
  truncateSession: (id: string, messageId: string) =>
    apiRequest<{ success: boolean; messages: ChatMessage[] }>(
      `/ai-assistant/sessions/${id}/truncate`,
      { method: 'POST', body: JSON.stringify({ messageId }) }
    ),

  chat: (req: ChatRequestPayload, signal?: AbortSignal) =>
    apiRequest<ChatResponsePayload>('/ai-assistant/chat', {
      method: 'POST',
      body: JSON.stringify(req),
      signal,
    }),

  cancel: (sessionId: string) =>
    apiRequest<{ success: boolean; sessionId: string }>(
      `/ai-assistant/sessions/${sessionId}/cancel`,
      { method: 'POST' }
    ),

  testConnection: (modelId: string) =>
    apiRequest<{ success: boolean; message: string; detail?: string; latencyMs?: number }>(
      '/ai-assistant/test-connection',
      { method: 'POST', body: JSON.stringify({ modelId }) }
    ),

  extractFile: (filename: string, contentBase64: string) =>
    apiRequest<{ success: boolean; text: string; error?: string }>(
      '/ai-assistant/extract-file',
      { method: 'POST', body: JSON.stringify({ filename, content_base64: contentBase64 }) }
    ),

  transcribe: (audioBase64: string, language = 'zh', modelSize = 'base') =>
    apiRequest<{ success: boolean; text: string; error?: string; language?: string }>(
      '/ai-assistant/transcribe',
      { method: 'POST', body: JSON.stringify({ audio_base64: audioBase64, language, model_size: modelSize }) }
    ),

  listSkills: () =>
    apiRequest<{ count: number; skills: any[] }>('/ai-assistant/skills'),

  listMemories: () =>
    apiRequest<{ entries: any[] }>('/ai-assistant/memories'),

  addMemory: (content: string, tags: string[] = []) =>
    apiRequest('/ai-assistant/memories', {
      method: 'POST',
      body: JSON.stringify({ content, tags }),
    }),

  deleteMemory: (id: string) =>
    apiRequest(`/ai-assistant/memories/${id}`, { method: 'DELETE' }),

}
