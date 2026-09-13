import type { ApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'
export type InspectionSession = components['schemas']['InspectionRead']
export type InspectionPick = components['schemas']['InspectionPick']
export type InspectionResult = components['schemas']['InspectionTestResult']
export type InspectionTest = components['schemas']['InspectionTest']
const path = (id?: string) => `/api/v1/workflows/inspection-sessions${id ? `/${encodeURIComponent(id)}` : ''}`
export function createInspectionApi(client: ApiClient) {
  return {
    current: () => client.request<InspectionSession | null>(path()),
    start: (sessionId: string, profileId: string) => client.request<InspectionSession>(path(), { method: 'POST', body: { sessionId, profileId } }),
    close: (id: string) => client.request<InspectionSession>(`${path(id)}/close`, { method: 'POST', timeoutMs: 120_000 }),
    page: (id: string, body: components['schemas']['InspectionPageCommand']) => client.request<InspectionSession>(`${path(id)}/page`, { method: 'POST', body, timeoutMs: 20_000 }),
    pick: (id: string, requestId: string, pageId: string) => client.request<InspectionPick>(`${path(id)}/picks`, { method: 'POST', body: { requestId, pageId }, timeoutMs: 20_000 }),
    getPick: (id: string, requestId: string) => client.request<InspectionPick>(`${path(id)}/picks/${encodeURIComponent(requestId)}`),
    cancel: (id: string, requestId: string) => client.request<InspectionPick>(`${path(id)}/picks/${encodeURIComponent(requestId)}/cancel`, { method: 'POST', timeoutMs: 20_000 }),
    test: (id: string, body: InspectionTest) => client.request<InspectionResult>(`${path(id)}/test-selector`, { method: 'POST', body, timeoutMs: 20_000 }),
  }
}
export type InspectionApi = ReturnType<typeof createInspectionApi>
export const inspectionActive = (session: InspectionSession | null) => Boolean(session && !['closed', 'failed'].includes(session.state))
