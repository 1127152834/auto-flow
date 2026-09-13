import type { ApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'

export type AndroidDevice = components['schemas']['AndroidDeviceRead']
export type AndroidEnvironment = components['schemas']['AndroidEnvironment']
export const androidApi = (client: ApiClient) => ({
  devices: () => client.request<AndroidDevice[]>('/api/v1/android/devices'),
  environment: () => client.request<AndroidEnvironment>('/api/v1/android/environment'),
})
