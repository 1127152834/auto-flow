export type AppState =
  | { status: 'loading' }
  | { status: 'connected'; instanceId: string; apiVersion: string }
  | { status: 'offline'; message: string }

export const initialAppState: AppState = { status: 'loading' }
