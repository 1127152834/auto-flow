import type { ApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'

export type ExecutionSettings = components['schemas']['ExecutionSettingsRead']

export type ExecutionSettingsApi = {
  read(): Promise<ExecutionSettings>
  save(maxRunningBrowsers: number | null, expectedRevision: number): Promise<ExecutionSettings>
}

// Remediation M1 R1-07/R1-11: machine-level browser limit.
export function createExecutionSettingsApi(client: ApiClient): ExecutionSettingsApi {
  return {
    read: () => client.request<ExecutionSettings>('/api/v1/settings/execution'),
    save: (maxRunningBrowsers, expectedRevision) => client.request<ExecutionSettings>('/api/v1/settings/execution', {
      method: 'PUT',
      body: { maxRunningBrowsers, expectedRevision },
    }),
  }
}
