import type { StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'

export type CheckStatus = components['schemas']['EnvironmentCheckRead']['status']
export type EnvironmentCheck = components['schemas']['EnvironmentCheckRead']
export type ManagementEnvironment = components['schemas']['ManagementEnvironmentRead']
export type ManagementCapabilities = components['schemas']['ManagementCapabilitiesRead']
export type ManagementDevicePage = components['schemas']['ManagementDevicePageRead']
export type OperationPage = components['schemas']['OperationPageRead']
export type Bulk = components['schemas']['BulkRead']
export type Image = components['schemas']['ImageRead']
export type Backup = components['schemas']['BackupRead']

const base = '/api/v1/android/management'
export const androidManagementApi = (client: StreamingApiClient) => ({
  environment: () => client.request<ManagementEnvironment>(`${base}/environment`, { timeoutMs: 20000 }),
  capabilities: () => client.request<ManagementCapabilities>(`${base}/capabilities`, { timeoutMs: 20000 }),
  devices: (query = '') => client.request<ManagementDevicePage>(`${base}/devices${query}`, { timeoutMs: 20000 }),
  operations: (query = '') => client.request<OperationPage>(`${base}/operations${query}`, { timeoutMs: 20000 }),
  images: () => client.request<{ items: Image[]; nextCursor: string | null; total: number }>(`${base}/images`, { timeoutMs: 20000 }),
  bulk: (body: Record<string, unknown>) => client.request<Bulk>(`${base}/bulk-operations`, { method: 'POST', body }),
  bulkAction: (id: string, body: Record<string, unknown>) => client.request<Bulk>(`${base}/bulk-operations/${id}/actions`, { method: 'POST', body }),
  cleanupPreview: (resourceIds: string[]) => client.request<{ items: Record<string, unknown>[]; confirmationDigest: string }>(`${base}/cleanup/previews`, { method: 'POST', body: { resourceIds } }),
  cleanup: (body: { requestId: string; confirmationDigest: string }) => client.request<{ items: Record<string, unknown>[]; state: string }>(`${base}/cleanup`, { method: 'POST', body }),
  diagnostics: (body: { requestId: string; deviceIds: string[]; includeAdvancedLogs?: boolean }) => client.request<components['schemas']['DiagnosticRead']>(`${base}/diagnostics`, { method: 'POST', body }),
  backups: () => client.request<Backup[]>(`${base}/backups`, { timeoutMs: 20000 }),
  backup: (body: { requestId: string; deviceId: string; expectedRevision: number }) => client.request<Backup>(`${base}/backups`, { method: 'POST', body, timeoutMs: 120000 }),
  restoreBackup: (id: string, body: { requestId: string; newName: string }) => client.request<Record<string, unknown>>(`${base}/backups/${id}/restore`, { method: 'POST', body, timeoutMs: 120000 }),
})
export type AndroidManagementApi = ReturnType<typeof androidManagementApi>
