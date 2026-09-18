import type { StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'
import type { GoogleSheetsBridge } from '../../../shared/google-sheets'
import { createOperationCommand } from './operation-command'

type Schema = components['schemas']
type Operation = Schema['ProjectOperationView']
export type SheetsConnection = Schema['SheetsConnection']
export type SheetsConnectionDirectory = Schema['SheetsConnectionDirectory']
export type SheetsBinding = Schema['SheetsBinding']
export type SheetsBindingWrite = Schema['SheetsBindingWrite']
export type SheetsInspection = Schema['SheetsInspection']
export type SheetsInspectionCreate = Schema['SheetsInspectionCreate']
export type SyncOperation = Schema['SyncOperation']
export type SyncOperationPage = Schema['SyncOperationPage']
export type SyncStateView = Schema['SyncStateView']
export type SyncSummary = Schema['SyncSummary']

export type SheetsInspectionOutcome = { operation: Operation; inspection: SheetsInspection | null }
export type SyncRunResult = Schema['SyncRunResult']
export type SheetsImpact = Schema['DataMutationImpact']
export type SheetsImpactBlocker = Schema['DataMutationBlocker']
export type SheetsImpactReport = Schema['SheetsImpactReport']

const tableLocator = (projectId: string, tableId: string) => ({ type: 'table' as const, projectId, tableId })
const connectionLocator = (projectId: string, connectionId: string) => ({
  type: 'sheetsConnection' as const,
  projectId,
  connectionId,
})

/**
 * One transport for every Sheets command. Acceptance is durable: a lost response is reconciled
 * through the original idempotency key, never by sending a second command under a new key.
 */
export function createSheetsApi(client: StreamingApiClient, desktop: Partial<GoogleSheetsBridge>, projectId: string) {
  const command = createOperationCommand(client, projectId)
  const base = `/api/v1/projects/${encodeURIComponent(projectId)}`
  const table = (tableId: string) => `${base}/tables/${encodeURIComponent(tableId)}`
  return {
    connections: () => client.request<SheetsConnectionDirectory>(`${base}/sheets/connections`),
    /** Ask the desktop host to run the Google handshake; the renderer only ever sees a token. */
    authorize: async (accountLabel: string) => {
      if (!desktop.connectGoogleSheets) throw new Error('当前窗口无法连接 Google 账号')
      const result = await desktop.connectGoogleSheets(projectId, accountLabel)
      if (!result.ok) throw Object.assign(new Error(result.error.message), result.error)
      return result.value
    },
    connect: async (accountLabel: string, authorizationToken: string, key: string, current: () => boolean) =>
      (await command.submit(`${base}/sheets/connections`, { accountLabel, authorizationToken }, key, 'connectSheets', current)),
    /**
     * The shared impact report every Sheets write quotes back. A command whose
     * confirmation went stale is refused before anything is stored, so the
     * caller re-previews instead of retrying the same revision.
     */
    previewBinding: (tableId: string, change: Schema['SheetsBindingChange'], signal?: AbortSignal) =>
      client.request<Schema['SheetsImpactReport']>(`${base}/mutation-impact`, {
        method: 'POST',
        ...(signal ? { signal } : {}),
        body: { action: 'changeSheetsBinding', target: tableLocator(projectId, tableId), change },
      }),
    previewUnbind: (tableId: string, signal?: AbortSignal) =>
      client.request<Schema['SheetsImpactReport']>(`${base}/mutation-impact`, {
        method: 'POST',
        ...(signal ? { signal } : {}),
        body: { action: 'removeSheetsBinding', target: tableLocator(projectId, tableId), change: { mode: 'remove' } },
      }),
    previewDisconnect: (connectionId: string, mode: Schema['SheetsDisconnectChange']['mode'], signal?: AbortSignal) =>
      client.request<Schema['SheetsImpactReport']>(`${base}/mutation-impact`, {
        method: 'POST',
        ...(signal ? { signal } : {}),
        body: { action: 'disconnectSheets', target: connectionLocator(projectId, connectionId), change: { mode } },
      }),
    disconnect: async (connectionId: string, body: Schema['SheetsConnectionDelete'], key: string, current: () => boolean) =>
      (await command.submit(`${base}/sheets/connections/${encodeURIComponent(connectionId)}`, body, key, 'disconnectSheets', current)),
    lookupDisconnect: async (key: string, current: () => boolean) => (await command.lookup(key, 'disconnectSheets', current)),
    readBinding: (tableId: string, signal?: AbortSignal) =>
      client.request<SheetsBinding | null>(`${table(tableId)}/sheets/binding`, signal ? { signal } : undefined),
    inspect: async (tableId: string, body: SheetsInspectionCreate, key: string, current: () => boolean) => {
      const operation = (await command.submit(`${table(tableId)}/sheets/inspect`, body, key, 'inspectSheets', current))
      // The inspection rides on the operation result, so a lost response is recoverable by key.
      const inspection = (operation.result as { inspection?: SheetsInspection } | null)?.inspection ?? null
      return { operation, inspection } satisfies SheetsInspectionOutcome
    },
    lookupInspection: async (tableId: string, key: string, current: () => boolean, signal?: AbortSignal) =>
      command.lookup(key, 'inspectSheets', current, signal),
    putBinding: async (tableId: string, body: SheetsBindingWrite, key: string, current: () => boolean) =>
      (await command.submit(`${table(tableId)}/sheets/binding`, body, key, 'changeSheetsBinding', current)),
    lookupBinding: async (key: string, current: () => boolean) =>
      (await command.lookup(key, 'changeSheetsBinding', current)),
    /** Removing a binding keeps the local copy; the confirmation says as much. */
    removeBinding: async (tableId: string, body: Schema['SheetsBindingDelete'], key: string, current: () => boolean) =>
      (await command.submit(`${table(tableId)}/sheets/binding`, body, key, 'removeSheetsBinding', current, 'DELETE')),
    lookupRemoveBinding: async (key: string, current: () => boolean) =>
      (await command.lookup(key, 'removeSheetsBinding', current)),
    state: (tableId: string, signal?: AbortSignal) =>
      client.request<SyncStateView>(`${table(tableId)}/sync`, signal ? { signal } : undefined),
    pull: async (tableId: string, expectedTableRevision: number, key: string, current: () => boolean) =>
      (await command.submit(`${table(tableId)}/sync/pull`, { expectedTableRevision }, key, 'syncPull', current)),
    lookupPull: async (key: string, current: () => boolean) => (await command.lookup(key, 'syncPull', current)),
    push: async (tableId: string, mode: 'due' | 'allPending', expectedBindingEpoch: number, key: string, current: () => boolean) =>
      (await command.submit(`${table(tableId)}/sync/push`, { mode, expectedBindingEpoch }, key, 'syncPush', current)),
    lookupPush: async (key: string, current: () => boolean) => (await command.lookup(key, 'syncPush', current)),
    /** Pause and resume are synchronous facts, not Operations; they carry the binding epoch as CAS. */
    pause: (tableId: string, expectedBindingEpoch: number) =>
      client.request<SyncStateView>(`${table(tableId)}/sync/pause`, { method: 'POST', headers: { 'Idempotency-Key': crypto.randomUUID() }, body: { expectedBindingEpoch } }),
    resume: (tableId: string, expectedBindingEpoch: number) =>
      client.request<SyncStateView>(`${table(tableId)}/sync/resume`, { method: 'POST', headers: { 'Idempotency-Key': crypto.randomUUID() }, body: { expectedBindingEpoch } }),
    operations: (tableId: string, query: { status?: string; page?: number; pageSize?: number } = {}, signal?: AbortSignal) => {
      const search = new URLSearchParams()
      if (query.status) search.set('status', query.status)
      search.set('page', String(query.page ?? 1))
      search.set('pageSize', String(query.pageSize ?? 50))
      return client.request<SyncOperationPage>(`${table(tableId)}/sync-operations?${search.toString()}`, signal ? { signal } : undefined)
    },
    operation: (tableId: string, syncOperationId: string, signal?: AbortSignal) =>
      client.request<SyncOperation>(`${table(tableId)}/sync-operations/${encodeURIComponent(syncOperationId)}`, signal ? { signal } : undefined),
    reconcile: async (tableId: string, syncOperationId: string, expectedStatusRevision: number, key: string, current: () => boolean) =>
      (await command.submit(`${table(tableId)}/sync-operations/${encodeURIComponent(syncOperationId)}/reconcile`, { expectedStatusRevision }, key, 'reconcileSync', current)),
    lookupReconcile: async (key: string, current: () => boolean) => (await command.lookup(key, 'reconcileSync', current)),
    abandon: async (tableId: string, syncOperationId: string, body: Schema['SyncAbandonRequest'], current: () => boolean) => {
      if (!current()) throw new Error('当前上下文已失效')
      return client.request<SyncOperation>(`${table(tableId)}/sync-operations/${encodeURIComponent(syncOperationId)}/abandon`, {
        method: 'POST',
        headers: { 'Idempotency-Key': crypto.randomUUID() },
        body,
      })
    },
  }
}
export type SheetsApi = ReturnType<typeof createSheetsApi>

export function newSheetsKey() {
  return crypto.randomUUID()
}
