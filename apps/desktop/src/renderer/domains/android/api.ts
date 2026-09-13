import type { StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'

export type AndroidDevice = components['schemas']['AndroidDeviceRead']
export type AndroidEnvironment = components['schemas']['AndroidEnvironment']
export type AndroidCreate = components['schemas']['AndroidCreate']
export type DeviceCommand = components['schemas']['AndroidDeviceCommand']
const base = '/api/v1/android'
export const androidApi = (client: StreamingApiClient) => ({
  devices: () => client.request<AndroidDevice[]>(`${base}/devices`, { timeoutMs: 60000 }),
  environment: () => client.request<AndroidEnvironment>(`${base}/environment`, { timeoutMs: 20000 }),
  create: (body: AndroidCreate) => client.request<AndroidDevice>(`${base}/devices`, { method: 'POST', body }),
  operate: (id: string, body: DeviceCommand) => client.request<AndroidDevice>(`${base}/devices/${id}/operations`, { method: 'POST', body }),
  rename: (id: string, name: string) => client.request<AndroidDevice>(`${base}/devices/${id}`, { method: 'PATCH', body: { name } }),
  preview: async (id: string, signal: AbortSignal) => (await client.stream(`${base}/devices/${id}/preview`, { signal })).blob(),
})
export type AndroidApi = ReturnType<typeof androidApi>
