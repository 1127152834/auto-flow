import { contextBridge, ipcRenderer } from 'electron'
import type { PlatformPaths } from '../main/platform/paths'
import type { SidecarStatus } from '../main/sidecar/supervisor'
import type { CopyProxyCredentialsRequest } from '../main/ipc/proxy-credentials'
import type { KernelRef } from '../main/ipc/kernel-paths'
import type { SettingsBridge, UiPreferences } from '../shared/settings'
import type { AutomationStudioBridge, StudioLeaveRequest } from '../shared/automation-studio'
import type { ExternalLinkBridge } from '../shared/external-links'
import type { ProjectFileBridge } from '../shared/project-files'
import type { GoogleSheetsBridge } from '../shared/google-sheets'
import type { DesktopRuntimeContext } from '../shared/runtime'
import type { StudioPlatformBridge } from '../shared/studio-platform'

const automationStudioBridge: AutomationStudioBridge = {
  openAutomationStudio: () => ipcRenderer.invoke('autoflow:open-automation-studio'),
  onStudioTransitionEnd:handler=>{
    const listener=()=>handler()
    ipcRenderer.on('autoflow:studio-transition-end',listener)
    return()=>{ipcRenderer.removeListener('autoflow:studio-transition-end',listener)}
  },
  onPrepareStudioLeave: handler => {
    let active=true
    const listener=async(_event:Electron.IpcRendererEvent,request:StudioLeaveRequest)=>{
      let allowed=false
      try{allowed=active&&await handler(request)}catch{allowed=false}
      await ipcRenderer.invoke('autoflow:studio-leave-result',{id:request.id,allowed:active&&allowed}).catch(()=>undefined)
    }
    ipcRenderer.on('autoflow:studio-prepare-leave',listener)
    void ipcRenderer.invoke('autoflow:studio-leave-ready').catch(()=>undefined)
    return()=>{active=false;ipcRenderer.removeListener('autoflow:studio-prepare-leave',listener)}
  },
}

const externalLinkBridge: ExternalLinkBridge = { openExternalLink: url => ipcRenderer.invoke('autoflow:open-external-link', url) }

const projectFileBridge: ProjectFileBridge = {
  getProjectFileContext: () => ipcRenderer.invoke('autoflow:project-files:context'),
  chooseExcelInput: projectId => ipcRenderer.invoke('autoflow:project-files:choose-excel-input', projectId),
  chooseXlsxOutput: (projectId, suggestedName) => ipcRenderer.invoke('autoflow:project-files:choose-xlsx-output', projectId, suggestedName),
}

const googleSheetsBridge: GoogleSheetsBridge = { connectGoogleSheets: (projectId, accountLabel) => ipcRenderer.invoke('autoflow:google-sheets:connect', projectId, accountLabel) }
const studioPlatformBridge:StudioPlatformBridge={runStudioPlatformAction:request=>ipcRenderer.invoke('autoflow:studio-platform-action',request)}

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
  ...googleSheetsBridge,
  ...externalLinkBridge,
  ...studioPlatformBridge,
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
