import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'
type Operation = components['schemas']['ProjectOperationView']
const encode = encodeURIComponent
const definitive = (error: unknown) => error instanceof ApiClientError && error.status >= 400 && error.status < 500 && error.status !== 408
const mismatch = () => new Error('操作结果与当前保存请求不一致')

export class DataCommandUncertain extends Error {
  constructor(readonly cause: unknown) {
    super('上次保存结果尚未确认，请先核对结果。')
    this.name = 'DataCommandUncertain'
  }
}

export type DataCommandPolicy = {
  acceptedResponse?: boolean
  lookupOnly?: boolean
  canSubmit?: () => boolean
}

export class DataCommandNotAccepted extends Error {
  constructor() {
    super('原操作尚未接受，可在当前上下文允许时重试原请求')
    this.name = 'DataCommandNotAccepted'
  }
}

export function assertFiniteNumbers(value: unknown): void {
  if (typeof value === 'number' && !Number.isFinite(value)) throw new Error('数值必须是有限数字，不能将无效数字写成空值')
  if (Array.isArray(value)) value.forEach(assertFiniteNumbers)
  else if (value && typeof value === 'object') Object.values(value).forEach(assertFiniteNumbers)
}

export function createDataCommand(client: StreamingApiClient, projectId: string) {
  async function command<T>(
    path: string,
    method: 'POST' | 'PATCH' | 'PUT' | 'DELETE',
    body: object,
    key: string,
    kind: Operation['kind'],
    resume: boolean,
    projectResult: (operation: Operation) => T,
    policy: DataCommandPolicy = {},
  ): Promise<T> {
    const originalBody = structuredClone(body)
    assertFiniteNumbers(originalBody)

    const project = (operation: Operation): T => {
      if (!operation || operation.projectId !== projectId || operation.idempotencyKey !== key || operation.kind !== kind || operation.status !== 'succeeded') throw mismatch()
      return projectResult(operation)
    }

    const submit = async (): Promise<T> => {
      if (policy.canSubmit && !policy.canSubmit()) {
        throw new DataCommandUncertain(new Error('当前上下文不允许发送原请求'))
      }
      if (!policy.acceptedResponse) {
        return client.request<T>(path, { method, headers: { 'Idempotency-Key': key }, body: originalBody })
      }
      const accepted = await client.request<{ operation: Operation }>(path, {
        method,
        headers: { 'Idempotency-Key': key },
        body: originalBody,
      })
      return project(accepted.operation)
    }

    if (!resume && !policy.lookupOnly) {
      try { return await submit() } catch (error) {
        if (definitive(error) || error instanceof DataCommandUncertain || (error instanceof DOMException && error.name === 'AbortError')) throw error
      }
    }
    try {
      const operation = await client.request<Operation>(`/api/v1/projects/${encode(projectId)}/operations/by-idempotency-key/${encode(key)}`)
      return project(operation)
    } catch (error) {
      if (!(error instanceof ApiClientError && error.status === 404 && error.code === 'OPERATION_NOT_FOUND')) throw new DataCommandUncertain(error)
      if (policy.lookupOnly) throw new DataCommandNotAccepted()
      try { return await submit() } catch (retryError) {
        if (definitive(retryError)) throw retryError
        throw new DataCommandUncertain(retryError)
      }
    }
  }

  return command
}
