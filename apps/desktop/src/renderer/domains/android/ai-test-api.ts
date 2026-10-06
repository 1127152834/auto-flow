import type { StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'
import { createModelApi } from '../models/api'

export type AiToolStatus = components['schemas']['AiToolStatusRead']
export type AiTestRunCreate = components['schemas']['AiTestRunCreate']
export type AiTestRun = components['schemas']['AiTestRunRead']
export type AiTestRunPage = components['schemas']['AiTestRunPageRead']
export type ExternalDevice = components['schemas']['ExternalDeviceRead']
export type AiTestHelperInstall = components['schemas']['AiTestHelperInstall']
export type AiTestTarget = { deviceKind: 'managed' | 'external'; deviceId?: string; serial?: string }

const base = '/api/v1/android/ai-tests'
const runPath = (id: string) => `${base}/runs/${encodeURIComponent(id)}`
const artifactPath = (id: string, name: string) => `${runPath(id)}/artifacts/${name.split('/').map(encodeURIComponent).join('/')}`

export const aiTestApi = (client: StreamingApiClient) => ({
  tool: () => client.request<AiToolStatus>(`${base}/tool`, { timeoutMs: 20000 }),
  installTool: (body: { requestId: string }) => client.request<AiToolStatus>(`${base}/tool/install`, { method: 'POST', body, timeoutMs: 120000 }),
  externalDevices: () => client.request<ExternalDevice[]>(`${base}/external-devices`, { timeoutMs: 20000 }),
  installHelper: (body: AiTestHelperInstall) => client.request<{ installed: boolean }>(`${base}/helper`, { method: 'POST', body, timeoutMs: 120000 }),
  start: (body: AiTestRunCreate) => client.request<AiTestRun>(`${base}/runs`, { method: 'POST', body, timeoutMs: 30000 }),
  runs: (target: AiTestTarget, cursor?: string) => {
    const query = new URLSearchParams({ deviceKind: target.deviceKind })
    if (target.deviceId) query.set('deviceId', target.deviceId)
    if (target.serial) query.set('serial', target.serial)
    if (cursor) query.set('cursor', cursor)
    return client.request<AiTestRunPage>(`${base}/runs?${query}`, { timeoutMs: 20000 })
  },
  run: (id: string) => client.request<AiTestRun>(runPath(id), { timeoutMs: 20000 }),
  cancel: (id: string) => client.request<AiTestRun>(`${runPath(id)}/cancel`, { method: 'POST', timeoutMs: 30000 }),
  remove: (id: string) => client.request<void>(runPath(id), { method: 'DELETE', timeoutMs: 20000 }),
  artifactUrl: artifactPath,
  // Artifacts need the auth header, so the page reads them as blobs instead of linking the URL directly.
  artifactBlob: async (id: string, name: string) => (await client.stream(artifactPath(id, name))).blob(),
  modelOptions: () => createModelApi(client).listOptions(),
})
export type AiTestApi = ReturnType<typeof aiTestApi>
