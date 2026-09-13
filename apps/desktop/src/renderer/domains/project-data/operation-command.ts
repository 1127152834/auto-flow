import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'
import { assertFiniteNumbers, DataCommandNotAccepted, DataCommandUncertain } from './data-command'

type Operation = components['schemas']['ProjectOperationView']
const definitive = (error: unknown) => error instanceof ApiClientError && error.status >= 400 && error.status < 500 && error.status !== 408

export class OperationIdentityMismatch extends Error {
  constructor() { super('操作结果与当前请求不一致'); this.name = 'OperationIdentityMismatch' }
}

/** Acceptance is a durable fact; callers observe its terminal result separately. */
export function createOperationCommand(client: StreamingApiClient, projectId: string) {
  const base = `/api/v1/projects/${encodeURIComponent(projectId)}/operations`
  const validate = (operation: Operation, key: string, kind: Operation['kind']) => {
    if (!operation || operation.projectId !== projectId || operation.idempotencyKey !== key || operation.kind !== kind) throw new OperationIdentityMismatch()
    return operation
  }
  const lookup = async (key: string, kind: Operation['kind'], current: () => boolean, signal?: AbortSignal) => {
    if (!current()) throw new DataCommandUncertain(new Error('当前上下文已失效'))
    try {
      const operation = await client.request<Operation>(`${base}/by-idempotency-key/${encodeURIComponent(key)}`, signal ? { signal } : undefined)
      if (!current()) throw new DataCommandUncertain(new Error('当前上下文已失效'))
      return validate(operation, key, kind)
    } catch (error) {
      if (error instanceof ApiClientError && error.status === 404 && error.code === 'OPERATION_NOT_FOUND') throw new DataCommandNotAccepted()
      throw error
    }
  }
  const submit = async (path: string, body: object, key: string, kind: Operation['kind'], current: () => boolean) => {
    if (!current()) throw new DataCommandUncertain(new Error('当前上下文已失效'))
    assertFiniteNumbers(body)
    let operation: Operation
    try {
      const response = await client.request<{ operation: Operation }>(path, { method: 'POST', headers: { 'Idempotency-Key': key }, body: structuredClone(body) })
      operation = response.operation
    } catch (error) {
      if (!current()) throw new DataCommandUncertain(new Error('当前上下文已失效'))
      if (definitive(error)) throw error
      try { operation = await lookup(key, kind, current) } catch (lookupError) {
        if (lookupError instanceof DataCommandNotAccepted || lookupError instanceof OperationIdentityMismatch) throw lookupError
        throw new DataCommandUncertain(lookupError)
      }
    }
    if (!current()) throw new DataCommandUncertain(new Error('当前上下文已失效'))
    return validate(operation, key, kind)
  }
  return { lookup, submit }
}
