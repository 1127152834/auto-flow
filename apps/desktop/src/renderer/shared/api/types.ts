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

export type HealthResponse = {
  status: 'ok'
  apiVersion: string
  instanceId: string
}

export type AutoflowBridge = {
  getSidecarStatus: () => Promise<SidecarStatus>
  restartSidecar: () => Promise<SidecarStatus>
}

declare global {
  interface Window {
    autoflow: AutoflowBridge
  }
}
