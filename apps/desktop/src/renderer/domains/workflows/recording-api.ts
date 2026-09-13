import type { ApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'
type Schema = components['schemas']
export type Recording = Schema['RecordingRead']
export type RecordingStep = Schema['RecordingStep']
export type RecordingGeneration = Schema['RecordingGeneration']
export type RecordingCommand = Schema['RecordingCommand']
const path = (id = '') => `/api/v1/workflows/recordings${id ? `/${encodeURIComponent(id)}` : ''}`
export const recordingActive = (record: Recording | null) => Boolean(record && ['starting', 'ready', 'closing'].includes(record.browserState))
export function createRecordingApi(client: ApiClient) {
  return {
    list: () => client.request<Schema['RecordingList']>(path()),
    get: (id: string) => client.request<Recording>(path(id)),
    start: (body: Schema['RecordingStart']) => client.request<Recording>(path(), { method: 'POST', body }),
    command: (id: string, body: RecordingCommand) => client.request<Schema['RecordingCommandRead']>(`${path(id)}/commands`, { method: 'POST', body }),
    readCommand: (id: string, commandId: string) => client.request<Schema['RecordingCommandRead']>(`${path(id)}/commands/${commandId}`),
    steps: (id: string, after = 0, ordered = true) => client.request<Schema['RecordingSteps']>(`${path(id)}/steps?afterSeq=${after}&ordered=${ordered}&limit=50`),
    value: (id: string, stepId: string) => client.request<Record<string, unknown>>(`${path(id)}/steps/${stepId}/value`),
    edit: (id: string, body: Schema['RecordingEdit']) => client.request<Recording>(`${path(id)}/steps`, { method: 'PATCH', body }),
    generate: (id: string, body: Schema['RecordingGenerate']) => client.request<RecordingGeneration>(`${path(id)}/generate`, { method: 'POST', body }),
    test: (id: string, body: Schema['InspectionTest']) => client.request<Schema['InspectionTestResult']>(`${path(id)}/test-selector`, { method: 'POST', body }),
    remove: (id: string) => client.request<void>(path(id), { method: 'DELETE' }),
  }
}
export type RecordingApi = ReturnType<typeof createRecordingApi>
