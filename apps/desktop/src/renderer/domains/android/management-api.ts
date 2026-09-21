import type { StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'

export type CheckStatus = components['schemas']['EnvironmentCheckRead']['status']
export type EnvironmentCheck = components['schemas']['EnvironmentCheckRead']
export type ManagementEnvironment = components['schemas']['ManagementEnvironmentRead']
export type ManagementCapabilities = components['schemas']['ManagementCapabilitiesRead']

const base = '/api/v1/android/management'
export const androidManagementApi = (client: StreamingApiClient) => ({
  environment: () => client.request<ManagementEnvironment>(`${base}/environment`, { timeoutMs: 20000 }),
  capabilities: () => client.request<ManagementCapabilities>(`${base}/capabilities`, { timeoutMs: 20000 }),
})
export type AndroidManagementApi = ReturnType<typeof androidManagementApi>
