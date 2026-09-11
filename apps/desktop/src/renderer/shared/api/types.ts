import type { components } from './generated'
import type { SettingsBridge } from '../../../shared/settings'

export type SidecarStatus =
  | { state: 'starting' | 'stopped' }
  | { state: 'failed'; message: string }
  | {
      state: 'ready'
      apiVersion: 'v1'
      instanceId: string
      port: number
      baseUrl: string
      token: string
    }

export type HealthResponse = components['schemas']['HealthResponse']
export type BrowserApiError = components['schemas']['BrowserApiError']
export type BrowserErrorEnvelope = components['schemas']['BrowserErrorEnvelope']
export type ProfileList = components['schemas']['ProfileList']
export type ProfileRead = components['schemas']['ProfileRead']
export type ProfileWrite = components['schemas']['ProfileWrite']
export type ProfileDuplicate = components['schemas']['ProfileDuplicate']
export type ProxyOptionsRead = components['schemas']['ProxyOptionsRead']
export type ProxyOption = components['schemas']['ProxyOption']
export type PoolOption = components['schemas']['PoolOption']
export type KernelCatalog = components['schemas']['KernelCatalogRead']
export type KernelRelease = components['schemas']['KernelReleaseRead']
export type InstalledKernel = components['schemas']['InstalledKernelRead']
export type InstalledKernelList = components['schemas']['InstalledKernelList']
export type License = components['schemas']['LicenseRead']
export type LicenseWrite = components['schemas']['LicenseWrite']
export type DefaultKernel = components['schemas']['DefaultKernelRead']
export type DefaultKernelWrite = components['schemas']['DefaultKernelWrite']
export type KernelDownload = components['schemas']['KernelDownload']
export type KernelOperation = components['schemas']['KernelOperationRead']
export type KernelOperationList = components['schemas']['KernelOperationList']
export type KernelRef = components['schemas']['KernelRefRead']

export type AutoflowBridge = Partial<SettingsBridge> & {
  getSidecarStatus: () => Promise<SidecarStatus>
  restartSidecar: () => Promise<SidecarStatus>
  copyProxyCredentials?: (request: { proxyId: string; protocol: 'http' | 'socks5'; format: 'username' | 'password' | 'url' }) => Promise<{ copied: true }>
  revealKernel?: (kernel: { edition: 'public' | 'licensed'; version: string }) => Promise<{ revealed: true }>
}

declare global {
  interface Window {
    autoflow: AutoflowBridge
  }
}
