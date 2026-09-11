import type { ModelApi } from '../domains/models/api'

export type AppState =
  | { status: 'loading' }
  | { status: 'connected'; instanceId: string; apiVersion: string; generation: number; modelApi: ModelApi }
  | { status: 'offline'; message: string }

export const initialAppState: AppState = { status: 'loading' }
