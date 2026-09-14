import { describe, expect, it, vi } from 'vitest'
import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import { createOperationCommand } from './operation-command'

function harness(responses: (() => unknown)[]) {
  const request = vi.fn(async () => responses.shift()!())
  return { request, client: { request } as unknown as StreamingApiClient }
}
const op = { projectId: 'p', idempotencyKey: 'key', kind: 'setRecordStatuses', operationId: 'op', status: 'running' }
describe('durable operation acceptance', () => {
  it('returns an accepted operation without claiming completion', async () => {
    const { client, request } = harness([() => ({ operation: op })])
    expect(await createOperationCommand(client, 'p').submit('/import', { name: 'A' }, 'key', 'setRecordStatuses', () => true)).toEqual(op)
    expect(request).toHaveBeenCalledTimes(1)
  })
  it('finds the original operation after losing the command response', async () => {
    const { client, request } = harness([() => { throw new TypeError('network') }, () => op])
    expect(await createOperationCommand(client, 'p').submit('/import', {}, 'key', 'setRecordStatuses', () => true)).toEqual(op)
    expect(request.mock.calls[1]).toEqual(['/api/v1/projects/p/operations/by-idempotency-key/key', undefined])
  })
  it('does not automatically resend when lookup proves the request was not accepted', async () => {
    const { client, request } = harness([() => { throw new TypeError('network') }, () => { throw new ApiClientError('not found', 404, 'OPERATION_NOT_FOUND') }])
    await expect(createOperationCommand(client, 'p').submit('/import', {}, 'key', 'setRecordStatuses', () => true)).rejects.toThrow('原操作尚未接受')
    expect(request).toHaveBeenCalledTimes(2)
  })
  it('does not send or project results after context is revoked', async () => {
    let allowed = true
    const { client } = harness([() => { allowed = false; return { operation: op } }])
    await expect(createOperationCommand(client, 'p').submit('/import', {}, 'key', 'setRecordStatuses', () => allowed)).rejects.toMatchObject({ cause: expect.objectContaining({ message: '当前上下文已失效' }) })
    const denied = harness([])
    await expect(createOperationCommand(denied.client, 'p').submit('/import', {}, 'key', 'setRecordStatuses', () => false)).rejects.toMatchObject({ cause: expect.objectContaining({ message: '当前上下文已失效' }) })
    expect(denied.request).not.toHaveBeenCalled()
  })
  it('rejects a result from another project or operation kind', async () => {
    const { client } = harness([() => ({ ...op, projectId: 'other' })])
    await expect(createOperationCommand(client, 'p').lookup('key', 'setRecordStatuses', () => true)).rejects.toThrow('不一致')
  })
  it('allows querying failed results with evidence but never retries definitive validation errors', async () => {
    const failed = { ...op, status: 'failed', error: { code: 'IMPORT_CONFLICT' } }
    const { client } = harness([() => failed])
    expect(await createOperationCommand(client, 'p').lookup('key', 'setRecordStatuses', () => true)).toEqual(failed)
    const invalid = harness([() => { throw new ApiClientError('invalid', 422, 'VALIDATION_ERROR') }])
    await expect(createOperationCommand(invalid.client, 'p').submit('/import', {}, 'key', 'setRecordStatuses', () => true)).rejects.toThrow('invalid')
    expect(invalid.request).toHaveBeenCalledTimes(1)
  })
})


it('rejects a lookup response after its context changes', async () => {
  let current = true
  const { client } = harness([() => { current = false; return op }])
  await expect(createOperationCommand(client, 'p').lookup('key', 'setRecordStatuses', () => current)).rejects.toMatchObject({ cause: expect.objectContaining({ message: '当前上下文已失效' }) })
})
it.each([{ projectId: 'other' }, { idempotencyKey: 'other' }, { kind: 'cancelRecordStatuses' }])('does not classify an identity mismatch as an uncertain result', async mismatch => {
  const { client } = harness([() => { throw new TypeError('lost') }, () => ({ ...op, ...mismatch })])
  await expect(createOperationCommand(client, 'p').submit('/import', {}, 'key', 'setRecordStatuses', () => true)).rejects.toMatchObject({ name: 'OperationIdentityMismatch' })
})
