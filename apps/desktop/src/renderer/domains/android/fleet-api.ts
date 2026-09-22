import type { StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'
export type Profile = components['schemas']['EnvironmentProfile']
export type Batch = components['schemas']['BatchRead']
export type BatchRequest = components['schemas']['BatchCreate']
export type Allocation = components['schemas']['AllocationRead']
export type AllocationRequest = components['schemas']['AllocationCreate']
export type ConsoleSession = components['schemas']['SessionRead']
export type InputCommand = components['schemas']['ControlCommand']
export type SessionAction = components['schemas']['SessionAction']['action']
export type Apps = components['schemas']['AppInfo']
export type DeviceRun = components['schemas']['DeviceRunRead']
const base = '/api/v1/android'
export const fleetApi = (client: StreamingApiClient) => ({
  profiles: () => client.request<Profile[]>(`${base}/profiles`, { timeoutMs: 25000 }),
  standardProfile: () => client.request<Profile>(`${base}/profiles/standard`, { method: 'POST', timeoutMs: 25000 }),
  saveProfile: (body: Profile) => client.request<Profile>(`${base}/profiles/${body.id}`, { method: 'PUT', body }),
  batches: () => client.request<Batch[]>(`${base}/batches`),
  batch: (body: BatchRequest) => client.request<Batch>(`${base}/batches`, { method: 'POST', body }),
  batchAction: (id: string, action: 'retry' | 'cancel') =>
    client.request<Batch>(`${base}/batches/${id}/actions`, { method: 'POST', body: { action } }),
  allocations: () => client.request<Allocation[]>(`${base}/allocations`),
  allocate: (body: AllocationRequest) => client.request<Allocation>(`${base}/allocations`, { method: 'POST', body }),
  cancelAllocation: (id: string) => client.request<Allocation>(`${base}/allocations/${id}`, { method: 'DELETE' }),
  history: (id: string, offset = 0) => client.request<DeviceRun[]>(`${base}/devices/${id}/runs?offset=${offset}&limit=50`),
  session: (deviceId: string, access: 'manual' | 'readonly', requestId: string) =>
    client.request<ConsoleSession>(`${base}/sessions`, {
      method: 'POST',
      body: { deviceId, access, requestId, clientSessionId: requestId },
      timeoutMs: 60000,
    }),
  readSession: (id: string) => client.request<ConsoleSession>(`${base}/sessions/${id}`),
  heartbeat: (session: ConsoleSession, clientSessionId: string) =>
    client.request<ConsoleSession>(`${base}/sessions/${session.id}/heartbeat`, { method: 'POST', body: { clientSessionId, generation: session.generation } }),
  action: (session: ConsoleSession, action: SessionAction, requestId = crypto.randomUUID()) =>
    client.request<ConsoleSession>(`${base}/sessions/${session.id}/actions`, {
      method: 'POST',
      body: { generation: session.generation, action, requestId },
      timeoutMs: 60000,
    }),
  input: (id: string, body: InputCommand) =>
    client.request<ConsoleSession>(`${base}/sessions/${id}/input`, { method: 'POST', body }),
  stream: (id: string, signal: AbortSignal) => client.stream(`${base}/sessions/${id}/stream`, { signal }),
  apps: (id: string) => client.request<Apps>(`${base}/sessions/${id}/apps`, { timeoutMs: 30000 }),
  launch: (s: ConsoleSession, packageName: string, requestId = crypto.randomUUID()) =>
    client.request<ConsoleSession>(`${base}/sessions/${s.id}/apps/launch`, {
      method: 'POST',
      body: { requestId, generation: s.generation, packageName },
      timeoutMs: 40000,
    }),
  appAction: (s: ConsoleSession, action: 'stop' | 'uninstall' | 'clearData', packageName: string, requestId = crypto.randomUUID()) =>
    client.request<ConsoleSession>(`${base}/sessions/${s.id}/apps/actions`, { method: 'POST', body: { requestId, generation: s.generation, action, packageName }, timeoutMs: 40000 }),
  verifyApp: (s: ConsoleSession, requestId: string, generation = s.generation) =>
    client.request<ConsoleSession>(`${base}/sessions/${s.id}/apps/verify`, { method: 'POST', body: { requestId, generation }, timeoutMs: 40000 }),
  install: (s: ConsoleSession, file: File, requestId = crypto.randomUUID()) => {
    const body = new FormData()
    body.append('file', file)
    return client.request<ConsoleSession>(`${base}/sessions/${s.id}/apps/install?generation=${s.generation}&requestId=${encodeURIComponent(requestId)}`, {
      method: 'POST', body, timeoutMs: 150000,
    })
  },
})
export type FleetApi = ReturnType<typeof fleetApi>
