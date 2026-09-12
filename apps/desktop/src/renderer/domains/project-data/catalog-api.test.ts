import { expect, it, vi } from 'vitest'
import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import { DataCommandUncertain } from './api'
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
function api(request: StreamingApiClient['request']) { return createDataCatalogApi({ request, health: vi.fn(), stream: vi.fn() }, scope) }

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
  expect(request.mock.calls[0]).toEqual(['/api/v1/projects/p/tables/t/fields', { signal }])
  expect(request.mock.calls[1]).toEqual(['/api/v1/projects/p/tables/t/statuses', { signal }])
  expect(request.mock.calls[2]).toEqual(['/api/v1/projects/p/mutation-impact', { method: 'POST', signal, body: { action: 'updateField', target: { type: 'field', fieldRef: ref }, change: definition } }])
})
