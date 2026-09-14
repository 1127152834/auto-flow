import { contextBridge, ipcRenderer } from 'electron'
import type { PlatformPaths } from '../main/platform/paths'
import type { SidecarStatus } from '../main/sidecar/supervisor'
import type { CopyProxyCredentialsRequest } from '../main/ipc/proxy-credentials'
import type { KernelRef } from '../main/ipc/kernel-paths'
import type { SettingsBridge, UiPreferences } from '../shared/settings'
import type { AutomationStudioBridge } from '../shared/automation-studio'
import type { ExternalLinkBridge } from '../shared/external-links'
import type { ProjectFileBridge } from '../shared/project-files'
import type { DesktopRuntimeContext } from '../shared/runtime'

const automationStudioBridge: AutomationStudioBridge = {
  openAutomationStudio: () => ipcRenderer.invoke('autoflow:open-automation-studio'),
}

const externalLinkBridge: ExternalLinkBridge = { openExternalLink: url => ipcRenderer.invoke('autoflow:open-external-link', url) }

const projectFileBridge: ProjectFileBridge = {
  getProjectFileContext: () => ipcRenderer.invoke('autoflow:project-files:context'),
  chooseExcelInput: projectId => ipcRenderer.invoke('autoflow:project-files:choose-excel-input', projectId),
  chooseXlsxOutput: (projectId, suggestedName) => ipcRenderer.invoke('autoflow:project-files:choose-xlsx-output', projectId, suggestedName),
}

const settingsBridge: SettingsBridge = {
  getSettings: () => ipcRenderer.invoke('autoflow:settings:get'),
  setPreferences: preferences => ipcRenderer.invoke('autoflow:settings:preferences', preferences),
  chooseWorkspace: source => ipcRenderer.invoke('autoflow:settings:choose-workspace', source),
  confirmWorkspace: id => ipcRenderer.invoke('autoflow:settings:confirm-workspace', id),
  openSettingsDirectory: directory => ipcRenderer.invoke('autoflow:settings:open-directory', directory),
  previewDiagnostics: includeLogs => ipcRenderer.invoke('autoflow:settings:preview-diagnostics', includeLogs),
  saveDiagnostics: id => ipcRenderer.invoke('autoflow:settings:save-diagnostics', id),
  quitApplication: () => ipcRenderer.invoke('autoflow:settings:quit'),
}
ipcRenderer.on('autoflow:preferences-changed', (_event, preferences: UiPreferences) => {
  document.documentElement.dataset.motion = preferences.motion
})

contextBridge.exposeInMainWorld('autoflow', {
  ...automationStudioBridge,
  ...settingsBridge,
  ...projectFileBridge,
  ...externalLinkBridge,
  getRuntimeContext: (): Promise<DesktopRuntimeContext> => ipcRenderer.invoke('autoflow:runtime-context'),
  onRuntimeContextChanged: (handler: (context: DesktopRuntimeContext) => void) => {
    const listener = (_event: Electron.IpcRendererEvent, context: DesktopRuntimeContext) => handler(context)
    ipcRenderer.on('autoflow:runtime-context-changed', listener)
    return () => { ipcRenderer.removeListener('autoflow:runtime-context-changed', listener) }
  },
  getSidecarStatus: (): Promise<SidecarStatus> => ipcRenderer.invoke('autoflow:sidecar-status'),
  restartSidecar: (): Promise<SidecarStatus> => ipcRenderer.invoke('autoflow:sidecar-restart'),
  getPlatformPaths: (): Promise<PlatformPaths> => ipcRenderer.invoke('autoflow:platform-paths'),
  copyProxyCredentials: (request: CopyProxyCredentialsRequest): Promise<{ copied: true }> => ipcRenderer.invoke('autoflow:copy-proxy-credentials', request),
  revealKernel: (kernel: KernelRef): Promise<{ revealed: true }> => ipcRenderer.invoke('autoflow:reveal-kernel', kernel),
})
