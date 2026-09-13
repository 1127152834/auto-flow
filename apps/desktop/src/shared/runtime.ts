import type { DesktopSettingsSnapshot, UiPreferences } from './settings'

export type SidecarStatus =
  | { state: 'starting' | 'stopped' }
  | { state: 'failed'; message: string }
  | { state: 'ready'; apiVersion: 'v1'; instanceId: string; port: number; baseUrl: string; token: string }

/** One main-process snapshot; workspace identity and service credentials must travel together. */
export type DesktopRuntimeContext = {
  workspaceKey: string
  sidecar: SidecarStatus
  preferences: UiPreferences
  operation: DesktopSettingsSnapshot['operation']
}

export type RuntimeBridge = {
  getRuntimeContext(): Promise<DesktopRuntimeContext>
  onRuntimeContextChanged(handler: (context: DesktopRuntimeContext) => void): () => void
}
