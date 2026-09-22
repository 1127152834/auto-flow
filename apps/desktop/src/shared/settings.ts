/** Desktop-only contracts shared by main, preload and renderer. No secrets. */
export type UiPreferences = { zoom: 90 | 100 | 110 | 125; motion: 'system' | 'reduce' | 'full' }
export type SettingsDirectory = 'workspace' | 'database' | 'profiles' | 'kernels' | 'logs'
export type DesktopResult<T> = { ok: true; value: T } | { ok: false; error: { code: string; message: string } }
export type DesktopSettingsSnapshot = {
  preferences: UiPreferences
  workspace: {
    path: string
    previousPath: string | null
    paths: Record<SettingsDirectory, string>
    blocked: boolean
    blockers: string[]
    recovery: string | null
    needsSelection: boolean
  }
  service: { state: 'starting' | 'ready' | 'failed' | 'stopped'; apiVersion: string | null; baseUrl: string | null; message: string | null }
  runtime: { appVersion: string; electronVersion: string; chromeVersion: string; nodeVersion: string; platform: 'macos' | 'windows' | 'linux'; arch: string; backendVersion: string | null; pythonVersion: string | null; sqliteVersion: string | null }
  operation: 'idle' | 'restarting' | 'switching' | 'exporting'
}
export type WorkspaceChoice = { id: string; path: string; kind: 'empty' | 'existing' }
export type DiagnosticPreview = { id: string; filename: string; content: string }
export type SettingsBridge = {
  getSettings(): Promise<DesktopResult<DesktopSettingsSnapshot>>
  setPreferences(preferences: UiPreferences): Promise<DesktopResult<UiPreferences>>
  chooseWorkspace(source: 'choose' | 'previous'): Promise<DesktopResult<WorkspaceChoice | null>>
  confirmWorkspace(id: string): Promise<DesktopResult<DesktopSettingsSnapshot>>
  openSettingsDirectory(directory: SettingsDirectory): Promise<DesktopResult<{ opened: true }>>
  previewDiagnostics(includeLogs: boolean): Promise<DesktopResult<DiagnosticPreview>>
  saveDiagnostics(id: string): Promise<DesktopResult<{ saved: boolean; path?: string }>>
  saveAndroidDiagnostic?(id: string): Promise<DesktopResult<{ saved: boolean; path?: string }>>
  quitApplication(): Promise<DesktopResult<{ quitting: true }>>
}
