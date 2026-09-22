import type { StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'

export type CheckStatus = components['schemas']['EnvironmentCheckRead']['status']
export type EnvironmentCheck = components['schemas']['EnvironmentCheckRead']
export type ManagementEnvironment = components['schemas']['ManagementEnvironmentRead']
export type ManagementCapabilities = components['schemas']['ManagementCapabilitiesRead']
export type ManagementDevicePage = components['schemas']['ManagementDevicePageRead']
export type OperationPage = components['schemas']['OperationPageRead']
export type Operation = components['schemas']['OperationRead']
export type Bulk = components['schemas']['BulkRead']
export type Image = components['schemas']['ImageRead']
export type Backup = components['schemas']['BackupRead']
export type BackupRestore = components['schemas']['BackupRestoreRead']
export type ImageRegister = components['schemas']['ImageRegister']
export type ImagePullCreate = components['schemas']['ImagePullCreate']
export type ImageDelete = components['schemas']['ImageDelete']
export type ImageVerificationCreate = components['schemas']['ImageVerificationCreate']

const base = '/api/v1/android/management'
export const androidManagementApi = (client: StreamingApiClient) => ({
  environment: () => client.request<ManagementEnvironment>(`${base}/environment`, { timeoutMs: 20000 }),
  capabilities: () => client.request<ManagementCapabilities>(`${base}/capabilities`, { timeoutMs: 20000 }),
  devices: (query = '') => client.request<ManagementDevicePage>(`${base}/devices${query}`, { timeoutMs: 20000 }),
  operations: (query = '') => client.request<OperationPage>(`${base}/operations${query}`, { timeoutMs: 20000 }),
  operation: (operationId: string) => client.request<Operation>(`${base}/operations/${encodeURIComponent(operationId)}`, { timeoutMs: 20000 }),
  operationByRequest: (requestId: string) => client.request<Operation>(`${base}/operations/by-request/${encodeURIComponent(requestId)}`, { timeoutMs: 20000 }),
  verify: (operationId: string, body: { requestId: string }) => client.request<Operation>(`${base}/operations/${encodeURIComponent(operationId)}/verify`, { method: 'POST', body, timeoutMs: 40000 }),
  images: () => client.request<{ items: Image[]; nextCursor: string | null; total: number }>(`${base}/images`, { timeoutMs: 20000 }),
  archiveProfile: (id: string, body: { requestId: string; expectedRevision: number }) => client.request<components['schemas']['EnvironmentProfile']>(`${base}/profiles/${id}/archive`, { method: 'POST', body }),
  registerImage: (body: ImageRegister) => client.request<Image>(`${base}/images`, { method: 'POST', body }),
  pullImage: (body: ImagePullCreate) => client.request<Operation>(`${base}/image-pulls`, { method: 'POST', body, timeoutMs: 120000 }),
  deleteImage: (identifier: string, body: ImageDelete) => client.request<Image>(`${base}/images/${encodeURIComponent(identifier)}`, { method: 'DELETE', body, timeoutMs: 120000 }),
  verifyImage: (identifier: string, body: ImageVerificationCreate) => client.request<Image>(`${base}/images/${encodeURIComponent(identifier)}/verifications`, { method: 'POST', body, timeoutMs: 40000 }),
  verifyImageDelete: (identifier: string, body: { requestId: string }) => client.request<Image>(`${base}/images/${encodeURIComponent(identifier)}/delete-verifications`, { method: 'POST', body, timeoutMs: 40000 }),
  bulk: (body: Record<string, unknown>) => client.request<Bulk>(`${base}/bulk-operations`, { method: 'POST', body }),
  bulkAction: (id: string, body: Record<string, unknown>) => client.request<Bulk>(`${base}/bulk-operations/${id}/actions`, { method: 'POST', body }),
  cleanupPreview: (resourceIds: string[]) => client.request<{ items: Record<string, unknown>[]; previewId?: string; confirmationDigest: string }>(`${base}/cleanup/previews`, { method: 'POST', body: { resourceIds } }),
  cleanup: (body: { requestId: string; previewId?: string; confirmationDigest: string }) => client.request<{ items: Record<string, unknown>[]; state: string; operationId?: string; requestId?: string; previewId?: string }>(`${base}/cleanup`, { method: 'POST', body }),
  diagnostics: (body: { requestId: string; deviceIds: string[]; includeAdvancedLogs?: boolean }) => client.request<components['schemas']['DiagnosticRead']>(`${base}/diagnostics`, { method: 'POST', body }),
  backups: () => client.request<Backup[]>(`${base}/backups`, { timeoutMs: 20000 }),
  backup: (body: { requestId: string; deviceId: string; expectedRevision: number }) => client.request<Backup>(`${base}/backups`, { method: 'POST', body, timeoutMs: 120000 }),
  restoreBackup: (id: string, body: { requestId: string; newName: string }) => client.request<BackupRestore>(`${base}/backups/${id}/restore`, { method: 'POST', body, timeoutMs: 120000 }),
})
export type AndroidManagementApi = ReturnType<typeof androidManagementApi>
