import type { ModelApi } from '../domains/models/api'
import type { StreamingApiClient } from '../shared/api/client'

export type AppState =
  | { status: 'loading' }
  | { status: 'connected'; instanceId: string; apiVersion: string; generation: number; modelApi: ModelApi; client: StreamingApiClient; baseUrl: string; token: string; workspaceKey: string }
  | { status: 'offline'; message: string }

export const initialAppState: AppState = { status: 'loading' }
