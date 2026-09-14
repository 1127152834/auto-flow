import { expect, it, vi } from 'vitest'
import { ApiClientError, createApiClient, type StreamingApiClient } from '../../shared/api/client'
import { DataCommandUncertain } from './api'
import { DataCommandNotAccepted } from './data-command'
import { createDataCatalogApi } from './catalog-api'

const scope = { projectId: 'p', tableId: 't', datasetGeneration: 'g' }
const ref = { ...scope, fieldId: 'f' }
const definition = { key: 'email', name: '邮箱', type: 'string' as const, required: false, validation: {} }
const field = { ...definition, ref, writable: true, formula: false, fieldRevision: 1 }
const fieldBody = { definition, expectedTableRevision: 1, sourceColumnPolicy: 'localOnly' as const }
const status = { statusId: 's', name: '就绪', color: '#aabbcc', order: 0, statusRevision: 1 }
const statusBody = { name: '就绪', color: '#aabbcc', order: 0, expectedTableRevision: 1 }
const fieldOperation = { projectId: 'p', idempotencyKey: 'k', kind: 'mutateField', status: 'succeeded', resource: { type: 'field', fieldRef: ref }, result: { action: 'create', field, tableRevision: 2 } }
const statusOperation = { ...fieldOperation, kind: 'mutateStatus', resource: { type: 'status', projectId: 'p', tableId: 't', statusId: 's' }, result: { action: 'create', status, tableRevision: 2 } }
const statusDelete = { action: 'delete' as const, statusId: 's', deleted: true as const, tableRevision: 3 }
const deletedStatusOperation = { ...statusOperation, result: statusDelete }
function api(request: StreamingApiClient['request']) { return createDataCatalogApi({ request, health: vi.fn(), stream: vi.fn() }, scope) }

it('projects only wire identity fields from a desktop editing context', async () => {
  const request = vi.fn().mockResolvedValue({})
  const context = { ...scope, workspaceKey: 'private-local-workspace' }
  await createDataCatalogApi({ request, health: vi.fn(), stream: vi.fn() }, context).previewField('f', definition)
  expect(request.mock.calls[0][1].body.target.fieldRef).toEqual(ref)
})

it('recovers field creation from the original immutable operation', async () => {
  const request = vi.fn().mockRejectedValueOnce(new TypeError('network')).mockResolvedValueOnce(fieldOperation)
  await expect(api(request).createField(fieldBody, 'k')).resolves.toEqual({ field, tableRevision: 2 })
  expect(request.mock.calls[1][0]).toBe('/api/v1/projects/p/operations/by-idempotency-key/k')
  expect(request).toHaveBeenCalledTimes(2)
})

it('recovers status creation and edits using distinct actions', async () => {
  const request = vi.fn().mockResolvedValueOnce(statusOperation).mockResolvedValueOnce({ ...statusOperation, result: { ...statusOperation.result, action: 'update' } })
  const catalog = api(request)
  await expect(catalog.createStatus(statusBody, 'k', true)).resolves.toEqual(status)
  await expect(catalog.updateStatus('s', { name: 'Done', expectedTableRevision: 2, expectedStatusRevision: 1 }, 'k', true)).resolves.toEqual(status)
  expect(request.mock.calls.every(call => String(call[0]).includes('/operations/by-idempotency-key/'))).toBe(true)
})

it('extracts status deletion from accepted and recovered operations', async () => {
  const request = vi.fn().mockResolvedValueOnce({ operation: deletedStatusOperation }).mockResolvedValueOnce(deletedStatusOperation)
  const catalog = api(request)
  const body = { expectedStatusRevision: 1, expectedTableRevision: 2, impactRevision: 7 }
  await expect(catalog.deleteStatus('s', body, 'k')).resolves.toEqual(statusDelete)
  await expect(catalog.deleteStatus('s', body, 'k', true, { lookupOnly: true })).resolves.toEqual(statusDelete)
  expect(request.mock.calls[0]).toEqual(['/api/v1/projects/p/tables/t/statuses/s', { method: 'DELETE', headers: { 'Idempotency-Key': 'k' }, body }])
  expect(request).toHaveBeenCalledTimes(2)
})

it.each([
  { ...deletedStatusOperation, resource: { ...deletedStatusOperation.resource, projectId: 'other' } },
  { ...deletedStatusOperation, resource: { ...deletedStatusOperation.resource, tableId: 'other' } },
  { ...deletedStatusOperation, resource: { ...deletedStatusOperation.resource, statusId: 'other' } },
  { ...deletedStatusOperation, result: { ...statusDelete, action: 'create' } },
  { ...deletedStatusOperation, result: { ...statusDelete, statusId: 'other' } },
  { ...deletedStatusOperation, result: { ...statusDelete, deleted: false } },
  { ...deletedStatusOperation, result: { ...statusDelete, tableRevision: NaN } },
  { ...deletedStatusOperation, result: { ...statusDelete, tableRevision: 0 } },
  { ...deletedStatusOperation, result: { ...statusDelete, tableRevision: 9_007_199_254_740_992 } },
])('rejects mismatched status deletion without resending', async wrong => {
  const request = vi.fn().mockResolvedValueOnce(wrong)
  await expect(api(request).deleteStatus('s', { expectedStatusRevision: 1, expectedTableRevision: 2, impactRevision: 7 }, 'k', true)).rejects.toBeInstanceOf(DataCommandUncertain)
  expect(request).toHaveBeenCalledTimes(1)
})

it.each(['createStatus', 'updateStatus'] as const)('does not let %s accept a delete result', async method => {
  const request = vi.fn().mockResolvedValueOnce(deletedStatusOperation)
  const catalog = api(request)
  const promise = method === 'createStatus'
    ? catalog.createStatus(statusBody, 'k', true)
    : catalog.updateStatus('s', { name: 'Done', expectedTableRevision: 2, expectedStatusRevision: 1 }, 'k', true)
  await expect(promise).rejects.toBeInstanceOf(DataCommandUncertain)
})

it.each([
  { ...fieldOperation, projectId: 'other' },
  { ...fieldOperation, idempotencyKey: 'wrong' },
  { ...fieldOperation, kind: 'mutateStatus' },
  { ...fieldOperation, status: 'accepted' },
  { ...fieldOperation, result: { ...fieldOperation.result, action: 'update' } },
  { ...fieldOperation, resource: { type: 'field', fieldRef: { ...ref, datasetGeneration: 'old' } } },
  { ...fieldOperation, result: { ...fieldOperation.result, field: { ...field, ref: { ...ref, fieldId: 'other' } } } },
])('does not resend or accept a mismatched recovered field operation', async wrong => {
  const request = vi.fn().mockResolvedValueOnce(wrong)
  await expect(api(request).createField(fieldBody, 'k', true)).rejects.toBeInstanceOf(DataCommandUncertain)
  expect(request).toHaveBeenCalledTimes(1)
})

it('checks the exact target for field and status edits', async () => {
  const request = vi.fn().mockResolvedValueOnce({ ...fieldOperation, result: { ...fieldOperation.result, action: 'update' } })
    .mockResolvedValueOnce({ ...statusOperation, result: { ...statusOperation.result, action: 'update' } })
  const catalog = api(request)
  await expect(catalog.updateField('wrong', { definition, expectedTableRevision: 1, expectedFieldRevision: 1, impactRevision: 1 }, 'k', true)).rejects.toBeInstanceOf(DataCommandUncertain)
  await expect(catalog.updateStatus('wrong', { name: 'x', expectedTableRevision: 1, expectedStatusRevision: 1 }, 'k', true)).rejects.toBeInstanceOf(DataCommandUncertain)
  expect(request).toHaveBeenCalledTimes(2)
})

it('resends only the original request after explicit operation-not-found', async () => {
  const body = structuredClone(statusBody)
  const request = vi.fn().mockImplementationOnce(async () => { body.name = 'new draft'; throw new TypeError('network') })
    .mockRejectedValueOnce(new ApiClientError('absent', 404, 'OPERATION_NOT_FOUND')).mockResolvedValueOnce(status)
  await expect(api(request).createStatus(body, 'k')).resolves.toEqual(status)
  expect(request.mock.calls[2]).toEqual(request.mock.calls[0])
  expect(request.mock.calls[2][1].body.name).toBe('就绪')
})

it.each([409, 412, 422])('preserves a definitive %s failure without lookup or retry', async code => {
  const error = new ApiClientError('conflict', code, 'CONFLICT')
  const request = vi.fn().mockRejectedValueOnce(error)
  await expect(api(request).createField(fieldBody, 'k')).rejects.toBe(error)
  expect(request).toHaveBeenCalledTimes(1)
})

it.each([new TypeError('offline'), new ApiClientError('missing project', 404, 'PROJECT_NOT_FOUND')])('keeps uncertain lookup failures without resending', async error => {
  const request = vi.fn().mockRejectedValueOnce(error)
  await expect(api(request).createStatus(statusBody, 'k', true)).rejects.toBeInstanceOf(DataCommandUncertain)
  expect(request).toHaveBeenCalledTimes(1)
})

it('passes cancellation to reads and uses a scoped pure impact request', async () => {
  const request = vi.fn().mockResolvedValue({})
  const catalog = api(request)
  const signal = new AbortController().signal
  await catalog.fields(signal)
  await catalog.statuses(signal)
  await catalog.previewField('f', definition, signal)
  await catalog.previewStatusDelete('s', signal)
  expect(request.mock.calls[0]).toEqual(['/api/v1/projects/p/tables/t/fields', { signal }])
  expect(request.mock.calls[1]).toEqual(['/api/v1/projects/p/tables/t/statuses', { signal }])
  expect(request.mock.calls[2]).toEqual(['/api/v1/projects/p/mutation-impact', { method: 'POST', signal, body: { action: 'updateField', target: { type: 'field', fieldRef: ref }, change: definition } }])
  expect(request.mock.calls[3]).toEqual(['/api/v1/projects/p/mutation-impact', { method: 'POST', signal, body: { action: 'deleteStatus', target: { type: 'status', projectId: 'p', tableId: 't', statusId: 's' } } }])
  expect(request.mock.calls[3][1]).not.toHaveProperty('headers')
})

it('passes a dynamic submit guard through every catalog write', async () => {
  const request = vi.fn().mockRejectedValue(new ApiClientError('absent', 404, 'OPERATION_NOT_FOUND'))
  const canSubmit = vi.fn(() => false)
  const catalog = api(request)
  const calls = [
    catalog.createField(fieldBody, 'k', true, { canSubmit }),
    catalog.updateField('f', { definition, expectedTableRevision: 1, expectedFieldRevision: 1, impactRevision: 1 }, 'k', true, { canSubmit }),
    catalog.createStatus(statusBody, 'k', true, { canSubmit }),
    catalog.updateStatus('s', { name: 'Done', expectedTableRevision: 2, expectedStatusRevision: 1 }, 'k', true, { canSubmit }),
  ]
  await Promise.all(calls.map(call => expect(call).rejects.toBeInstanceOf(DataCommandUncertain)))
  expect(canSubmit).toHaveBeenCalledTimes(4)
})

it('lookup-only status deletion never submits after operation-not-found', async () => {
  const request = vi.fn().mockRejectedValueOnce(new ApiClientError('absent', 404, 'OPERATION_NOT_FOUND'))
  await expect(api(request).deleteStatus('s', { expectedStatusRevision: 1, expectedTableRevision: 2, impactRevision: 7 }, 'k', false, { lookupOnly: true })).rejects.toBeInstanceOf(DataCommandNotAccepted)
  expect(request).toHaveBeenCalledTimes(1)
})

it('rejects a non-finite backfill default before actual JSON serialization', async () => {
  const fetcher = vi.fn()
  vi.stubGlobal('fetch', fetcher)
  try {
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:9999', token: 'test', timeoutMs: 0 })
    await expect(createDataCatalogApi(client, scope).createField({ ...fieldBody, existingRecordDefault: NaN }, 'k')).rejects.toThrow('有限数字')
    expect(fetcher).not.toHaveBeenCalled()
  } finally { vi.unstubAllGlobals() }
})


it('reads real status usage independently and passes abort scope', async () => {
  const request = vi.fn().mockResolvedValue({ datasetGeneration: 'g', items: [], configurationReferences: { availability: 'notImplemented' } });
  const signal = new AbortController().signal;
  await api(request).statusUsage(signal);
  expect(request).toHaveBeenCalledWith('/api/v1/projects/p/tables/t/statuses/usage', { signal });
});
