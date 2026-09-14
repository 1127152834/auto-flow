import type { components } from './generated'
import type { ExternalLinkBridge } from '../../../shared/external-links'
import type { ProjectFileBridge } from '../../../shared/project-files'
import type { SettingsBridge } from '../../../shared/settings'
import type { AutomationStudioBridge } from '../../../shared/automation-studio'
import type { RuntimeBridge, SidecarStatus } from '../../../shared/runtime'

export type { SidecarStatus } from '../../../shared/runtime'

export type HealthResponse = components['schemas']['HealthResponse']
export type BrowserApiError = components['schemas']['BrowserApiError']
export type BrowserErrorEnvelope = components['schemas']['BrowserErrorEnvelope']
export type ProfileList = components['schemas']['ProfileList']
export type ProfileRead = components['schemas']['ProfileRead']
export type ProfileTestBrowser = components['schemas']['ProfileTestBrowserRead']
export type ProfileTestBrowserList = components['schemas']['ProfileTestBrowserList']
export type ProfileWrite = components['schemas']['ProfileWrite']
export type ProfileDuplicate = components['schemas']['ProfileDuplicate']
export type ProfileEnvironmentOptions = components['schemas']['ProfileEnvironmentOptionsRead']
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

export type AutoflowBridge = Partial<SettingsBridge & AutomationStudioBridge & ProjectFileBridge & ExternalLinkBridge> & RuntimeBridge & {
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
