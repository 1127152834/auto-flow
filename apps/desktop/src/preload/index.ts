import { contextBridge, ipcRenderer } from 'electron'
import type { PlatformPaths } from '../main/platform/paths'
import type { SidecarStatus } from '../main/sidecar/supervisor'
import type { CopyProxyCredentialsRequest } from '../main/ipc/proxy-credentials'
import type { KernelRef } from '../main/ipc/kernel-paths'

contextBridge.exposeInMainWorld('autoflow', {
  getSidecarStatus: (): Promise<SidecarStatus> => ipcRenderer.invoke('autoflow:sidecar-status'),
  restartSidecar: (): Promise<SidecarStatus> => ipcRenderer.invoke('autoflow:sidecar-restart'),
  getPlatformPaths: (): Promise<PlatformPaths> => ipcRenderer.invoke('autoflow:platform-paths'),
  copyProxyCredentials: (request: CopyProxyCredentialsRequest): Promise<{ copied: true }> => ipcRenderer.invoke('autoflow:copy-proxy-credentials', request),
  revealKernel: (kernel: KernelRef): Promise<{ revealed: true }> => ipcRenderer.invoke('autoflow:reveal-kernel', kernel),
})
