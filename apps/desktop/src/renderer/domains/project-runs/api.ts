import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'
import { assertFiniteNumbers, DataCommandNotAccepted, DataCommandUncertain, type DataCommandPolicy } from '../project-data/data-command'

type Schema = components['schemas']
export type Batch = Schema['BatchView']; export type BatchPage = Schema['BatchPage']; export type BatchDetail = Schema['BatchDetail']; export type Task = Schema['TaskView']; export type TaskDetail = Schema['TaskDetail']; export type TaskPage = Schema['TaskPage']; export type BatchStartRequest = Schema['BatchStartRequest']; export type BatchStopRequest = Schema['BatchStopRequest']
export type RunOperation = Schema['ProjectOperationView'] | Schema['ProjectRunOperationSnapshot']
export type RunCommandOutcome = { state: 'accepted'; operation: RunOperation } | { state: 'succeeded'; batch: Batch }
class RunOperationFailed extends ApiClientError {}
export type BatchQuery = { q?: string; automationId?: string; status?: string; startedFrom?: string; startedTo?: string; page: number; pageSize: number; sort: string }
export type TaskQuery = { q?: string; automationId?: string; batchId?: string; status?: string; endedFrom?: string; endedTo?: string; page: number; pageSize: number; sort: string }
const encode = encodeURIComponent
const query = (value: Record<string, string | number | undefined>) => new URLSearchParams(Object.entries(value).filter((entry): entry is [string, string | number] => entry[1] !== undefined).map(([key, item]) => [key, String(item)])).toString()

export function createProjectRunsApi(client: StreamingApiClient, projectId: string) {
  const root = `/api/v1/projects/${encode(projectId)}`
  const command = async (path: string, kind: 'startBatch' | 'stopBatch' | 'forceStopBatch', expectedId: string, body: BatchStartRequest | BatchStopRequest, key: string, resume: boolean, policy: DataCommandPolicy = {}): Promise<RunCommandOutcome> => {
    const originalBody = structuredClone(body); assertFiniteNumbers(originalBody)
    const project = (operation: RunOperation): RunCommandOutcome => {
      if (operation.projectId !== projectId || operation.idempotencyKey !== key || operation.kind !== kind) throw new Error('操作结果与当前批次不一致')
      const resource = operation.resource as { type?: unknown; projectId?: unknown; batchId?: unknown }
      if (resource.type !== 'batch' || resource.projectId !== projectId || (kind !== 'startBatch' && resource.batchId !== expectedId)) throw new Error('操作资源与当前批次不一致')
      if (operation.status === 'failed') { const detail = operation.error as { message?: unknown } | null; throw new RunOperationFailed(typeof detail?.message === 'string' ? detail.message : '批次操作失败', 422, 'OPERATION_FAILED') }
      if (operation.status !== 'succeeded') return { state: 'accepted', operation }
      const result = operation.result as { batch?: Batch } | null
      if (!result?.batch || result.batch.projectId !== projectId || result.batch.batchId !== resource.batchId || (kind === 'startBatch' ? result.batch.automationId !== expectedId : result.batch.batchId !== expectedId)) throw new Error('操作结果与当前批次不一致')
      return { state: 'succeeded', batch: result.batch }
    }
    const submit = async () => {
      if (policy.canSubmit && !policy.canSubmit()) throw new DataCommandUncertain(new Error('当前上下文不允许发送原请求'))
      const accepted = await client.request<Schema['ProjectRunOperationAccepted']>(path, { method: 'POST', headers: { 'Idempotency-Key': key }, body: originalBody })
      return project(accepted.operation)
    }
    if (!resume && !policy.lookupOnly) try { return await submit() } catch (error) { if (error instanceof ApiClientError && error.status >= 400 && error.status < 500 && error.status !== 408) throw error }
    try { return project(await client.request<RunOperation>(`${root}/operations/by-idempotency-key/${encode(key)}`)) }
    catch (error) {
      if (error instanceof RunOperationFailed) throw error
      if (!(error instanceof ApiClientError && error.status === 404 && error.code === 'OPERATION_NOT_FOUND')) throw new DataCommandUncertain(error)
      if (policy.lookupOnly || policy.retryIfNotAccepted === false) throw new DataCommandNotAccepted()
      try { return await submit() } catch (retryError) { if (retryError instanceof ApiClientError && retryError.status >= 400 && retryError.status < 500 && retryError.status !== 408) throw retryError; throw new DataCommandUncertain(retryError) }
    }
  }
  return {
    listBatches: (filter: BatchQuery, signal?: AbortSignal) => client.request<BatchPage>(`${root}/batches?${query(filter)}`, { signal }),
    getBatch: (batchId: string, signal?: AbortSignal) => client.request<BatchDetail>(`${root}/batches/${encode(batchId)}`, { signal }),
    listTasks: (filter: TaskQuery, signal?: AbortSignal) => client.request<TaskPage>(`${root}/tasks?${query(filter)}`, { signal }),
    getTask: (taskId: string, signal?: AbortSignal) => client.request<TaskDetail>(`${root}/tasks/${encode(taskId)}`, { signal }),
    start: (automationId: string, body: BatchStartRequest, key: string, policy?: DataCommandPolicy) => command(`${root}/automations/${encode(automationId)}/batches`, 'startBatch', automationId, body, key, false, policy),
    resumeStart: (automationId: string, body: BatchStartRequest, key: string, policy?: DataCommandPolicy) => command(`${root}/automations/${encode(automationId)}/batches`, 'startBatch', automationId, body, key, true, policy),
    stop: (batchId: string, body: BatchStopRequest, key: string, policy?: DataCommandPolicy) => command(`${root}/batches/${encode(batchId)}/stop`, 'stopBatch', batchId, body, key, false, policy),
    resumeStop: (batchId: string, body: BatchStopRequest, key: string, policy?: DataCommandPolicy) => command(`${root}/batches/${encode(batchId)}/stop`, 'stopBatch', batchId, body, key, true, policy),
    forceStop: (batchId: string, body: BatchStopRequest, key: string, policy?: DataCommandPolicy) => command(`${root}/batches/${encode(batchId)}/force-stop`, 'forceStopBatch', batchId, body, key, false, policy),
    resumeForceStop: (batchId: string, body: BatchStopRequest, key: string, policy?: DataCommandPolicy) => command(`${root}/batches/${encode(batchId)}/force-stop`, 'forceStopBatch', batchId, body, key, true, policy),
  }
}
