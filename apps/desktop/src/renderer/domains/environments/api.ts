import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'
import { DataCommandNotAccepted, DataCommandUncertain } from '../project-data/data-command'
import { isDefinitiveProjectFailure } from '../projects/api'
import { createOperationCommand } from '../project-data/operation-command'

type Schema = components['schemas']
export type Environment = Schema['EnvironmentView']
export type EnvironmentDetail = Schema['EnvironmentDetailView']
export type EnvironmentPage = Schema['EnvironmentPage']
export type EnvironmentInstance = Schema['EnvironmentInstanceView']
export type EnvironmentInstancePage = Schema['EnvironmentInstancePage']
export type EnvironmentOperation = Schema['EnvironmentOperationView']
export type EnvironmentPatch = Schema['EnvironmentPatch']
export type EnvironmentEndRequest = Schema['EnvironmentEndRequest']
export type EnvironmentImpact = Schema['EnvironmentImpactView']
export type EnvironmentDeleteBody = Schema['EnvironmentDeleteRequest']
export type ManualItem = Schema['ManualItemView']
export type ManualSort = 'expiresAt' | '-updatedAt'
export type EnvironmentQuery = { query: string; page: number; pageSize: number; sort: 'name' | '-name' | 'updatedAt' | '-updatedAt'; state?: string }

const encode = encodeURIComponent

export function createEnvironmentApi(client: StreamingApiClient, projectId: string) {
  const base = `/api/v1/projects/${encode(projectId)}`
  // Environment deletes are stored in the same project operation table, so the
  // shared by-idempotency-key lookup recovers an uncertain outcome.
  const operations = createOperationCommand<Schema['EnvironmentOperationSnapshot']>(client, projectId)
  async function patchConfiguration(environmentId: string, body: EnvironmentPatch, key: string, resume = false): Promise<Environment> {
    const submit = () => client.request<Environment>(`${base}/environments/${encode(environmentId)}`, { method: 'PATCH', headers: { 'Idempotency-Key': key }, body })
    if (!resume) try { return await submit() } catch (error) { if (isDefinitiveProjectFailure(error)) throw error }
    try {
      const operation = await operations.lookup(key, 'updateEnvironment', () => true)
      if (operation.resource.environmentId !== environmentId) throw new DataCommandUncertain(new Error('操作环境不一致'))
      if (operation.status === 'failed') throw new ApiClientError(String(operation.error?.message ?? '保存失败'), Number(operation.error?.status ?? 409), String(operation.error?.code ?? 'CONFIGURATION_FAILED'))
      if (operation.status === 'succeeded') {
        const result = operation.result as Environment | null
        if (result?.ref.environmentId !== environmentId || result.ref.projectId !== projectId) throw new DataCommandUncertain(new Error('保存结果不一致'))
        return result
      }
    } catch (error) {
      if (isDefinitiveProjectFailure(error)) throw error
      if (!(error instanceof DataCommandNotAccepted)) throw new DataCommandUncertain(error)
    }
    // The same immutable command finishes a publication interrupted before DB commit.
    try { return await submit() } catch (error) { if (isDefinitiveProjectFailure(error)) throw error; throw new DataCommandUncertain(error) }
  }
  return {
    patchConfiguration,
    list: (query: EnvironmentQuery, signal?: AbortSignal) => {
      const state = query.state ? `&state=${encode(query.state)}` : ''
      return client.request<EnvironmentPage>(`${base}/environments?q=${encode(query.query)}&page=${query.page}&pageSize=${query.pageSize}&sort=${encode(query.sort)}${state}`, { signal })
    },
    get: (environmentId: string, signal?: AbortSignal) => client.request<EnvironmentDetail>(`${base}/environments/${encode(environmentId)}`, { signal }),
    getInstance: (instanceId: string, signal?: AbortSignal) => client.request<EnvironmentInstance>(`${base}/environment-instances/${encode(instanceId)}`, { signal }),
    listInstances: (query: { page: number; pageSize: number; state?: string; taskId?: string }, signal?: AbortSignal) => {
      const state = query.state ? `&state=${encode(query.state)}` : ''
      const taskId = query.taskId ? `&taskId=${encode(query.taskId)}` : ''
      return client.request<EnvironmentInstancePage>(`${base}/environment-instances?page=${query.page}&pageSize=${query.pageSize}${state}${taskId}`, { signal })
    },
    patch: (environmentId: string, body: EnvironmentPatch, key: string) => client.request<Environment>(`${base}/environments/${encode(environmentId)}`, {
      method: 'PATCH',
      headers: { 'Idempotency-Key': key },
      body,
    }),
    save: (body: Schema['EnvironmentSaveRequest'], key: string) => client.request<EnvironmentOperation>(`${base}/environment-saves`, {
      method: 'POST',
      headers: { 'Idempotency-Key': key },
      body,
    }),
    startMaintenance: (environmentId: string, expectedContentGeneration: number, key: string) => client.request<EnvironmentOperation>(`${base}/environments/${encode(environmentId)}/maintenance`, {
      method: 'POST',
      headers: { 'Idempotency-Key': key },
      body: { expectedContentGeneration },
    }),
    discardMaintenance: (environmentId: string, body: Schema['MaintenanceDiscardRequest'], key: string) => client.request<EnvironmentOperation>(`${base}/environments/${encode(environmentId)}/maintenance/discard`, {
      method: 'POST',
      headers: { 'Idempotency-Key': key },
      body,
    }),
    operation: (operationId: string, signal?: AbortSignal) => client.request<EnvironmentOperation>(`${base}/environment-operations/${encode(operationId)}`, { signal }),
    repair: (operationId: string, body: Schema['EnvironmentRepairRequest'], key: string) => client.request<EnvironmentOperation>(`${base}/environment-operations/${encode(operationId)}/repair`, {
      method: 'POST',
      headers: { 'Idempotency-Key': key },
      body,
    }),
    end: (taskId: string, body: EnvironmentEndRequest, key: string) => client.request<EnvironmentOperation>(`${base}/tasks/${encode(taskId)}/end`, {
      method: 'POST',
      headers: { 'Idempotency-Key': key },
      body,
    }),
    taskEnd: (taskId: string, signal?: AbortSignal) => client.request<Schema['TaskEndResultView'] | null>(`${base}/tasks/${encode(taskId)}/end`, { signal }),
    openInstance: (instanceId: string, expectedUseGeneration: number, key: string) => client.request<EnvironmentOperation>(`${base}/environment-instances/${encode(instanceId)}/open`, {
      method: 'POST',
      headers: { 'Idempotency-Key': key },
      body: { expectedUseGeneration },
    }),
    impact: (environmentId: string, signal?: AbortSignal) => client.request<EnvironmentImpact>(`${base}/environments/${encode(environmentId)}/impact?action=delete`, { signal }),
    remove: (environmentId: string, body: EnvironmentDeleteBody, key: string, current: () => boolean = () => true) => operations.submit(`${base}/environments/${encode(environmentId)}`, body, key, 'deleteEnvironment', current, 'DELETE'),
    listManual: (query: { page: number; pageSize: number; status?: string; q?: string; sort?: ManualSort }, signal?: AbortSignal) => {
      const params = new URLSearchParams({ page: String(query.page), pageSize: String(query.pageSize) })
      if (query.status) params.set('status', query.status)
      if (query.q) params.set('q', query.q)
      if (query.sort) params.set('sort', query.sort)
      return client.request<{ items: ManualItem[]; page: number; pageSize: number; total: number }>(`${base}/manual-items?${params.toString()}`, { signal })
    },
    getManual: (manualItemId: string, signal?: AbortSignal) => client.request<ManualItem>(`${base}/manual-items/${encode(manualItemId)}`, { signal }),
    lookupManualResume: (key: string) => operations.lookup(key, 'resumeManual', () => true),
    resumeManual: async (manualItemId: string, body: { checkpointRevision: number; expectedStatusRevision: number; targetNodeId?: string; inputs?: Record<string, unknown> }, key: string) => {
      const operation = await operations.submit(`${base}/manual-items/${encode(manualItemId)}/resume`, body, key, 'resumeManual', () => true)
      return { operation, outcome: operation.result }
    },
    finishManual: (manualItemId: string, body: Schema['ManualFinishRequest'], key: string) => client.request<EnvironmentOperation>(`${base}/manual-items/${encode(manualItemId)}/finish`, {
      method: 'POST',
      headers: { 'Idempotency-Key': key },
      body,
    }),
  }
}
