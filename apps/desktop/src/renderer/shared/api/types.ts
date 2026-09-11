import type { components } from './generated'

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

export type AutoflowBridge = {
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
