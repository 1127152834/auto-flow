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

function assertFiniteNumbers(value: unknown): void {
  if (typeof value === 'number' && !Number.isFinite(value)) throw new Error('数值必须是有限数字，不能将无效数字写成空值')
  if (Array.isArray(value)) value.forEach(assertFiniteNumbers)
  else if (value && typeof value === 'object') Object.values(value).forEach(assertFiniteNumbers)
}

export function createDataCommand(client: StreamingApiClient, projectId: string) {
  async function command<T>(path: string, method: 'POST' | 'PATCH' | 'PUT', body: object, key: string, kind: Operation['kind'], resume: boolean, projectResult: (operation: Operation) => T): Promise<T> {
    const originalBody = structuredClone(body)
    assertFiniteNumbers(originalBody)
    const submit = () => client.request<T>(path, { method, headers: { 'Idempotency-Key': key }, body: originalBody })
    if (!resume) {
      try { return await submit() } catch (error) {
        if (definitive(error) || (error instanceof DOMException && error.name === 'AbortError')) throw error
      }
    }
    try {
      const operation = await client.request<Operation>(`/api/v1/projects/${encode(projectId)}/operations/by-idempotency-key/${encode(key)}`)
      if (operation.projectId !== projectId || operation.idempotencyKey !== key || operation.kind !== kind || operation.status !== 'succeeded') throw mismatch()
      return projectResult(operation)
    } catch (error) {
      if (!(error instanceof ApiClientError && error.status === 404 && error.code === 'OPERATION_NOT_FOUND')) throw new DataCommandUncertain(error)
      try { return await submit() } catch (retryError) {
        if (definitive(retryError)) throw retryError
        throw new DataCommandUncertain(retryError)
      }
    }
  }

  return command
}
