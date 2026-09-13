import { expect, it, vi } from 'vitest'
import { ApiClientError, createApiClient, type StreamingApiClient } from '../../shared/api/client'
import { DataCommandUncertain } from './api'
import { createRecordsApi } from './records-api'

const scope = { projectId: 'p', tableId: 't', datasetGeneration: 'g' }
const ref = { ...scope, recordKey: { type: 'text' as const, value: '编号001 / 😀' } }
const record = { ref, values: [], statusId: null, currentEnvironmentId: null, contentRevision: 1, statusRevision: 1, linkRevision: 1, deleted: false, recordSlots: [], createdAt: '2026-09-13T00:00:00Z', updatedAt: '2026-09-13T00:00:00Z' }
const operation = { projectId: 'p', idempotencyKey: 'key', kind: 'createRecord', status: 'succeeded', resource: { type: 'record', recordRef: ref }, result: record }
const deleted = { target: { type: 'record' as const, recordRef: ref }, deleted: true as const }
const deleteOperation = { ...operation, kind: 'deleteRecord', result: deleted }
function api(request: StreamingApiClient['request']) { return createRecordsApi({ request, health: vi.fn(), stream: vi.fn() }, scope) }

it('encodes Unicode record identities as UTF8 base64url exactly once and keeps key type', async () => {
  const request = vi.fn().mockResolvedValueOnce(record)
  const signal = new AbortController().signal
  await api(request).get(ref.recordKey, signal)
  const [url, init] = request.mock.calls[0]
  const encodedKey = String(url).split('/records/')[1].split('?')[0]
  expect(Buffer.from(encodedKey, 'base64url').toString('utf8')).toBe(ref.recordKey.value)
  expect(url).toContain('recordKeyType=text'); expect(url).toContain('datasetGeneration=g')
  expect(init).toEqual({ signal })
})

it('encodes full filter and order before sending server-side pagination', async () => {
  const request = vi.fn().mockResolvedValueOnce({ items: [], total: 0 })
  const filter = { type: 'compare', fieldId: 'f', operator: 'contains', value: '中文&😀' }
  const orderBy = [{ fieldId: 'f', direction: 'desc' }]
  const signal = new AbortController().signal
  await api(request).list({ filter, orderBy, page: 3, pageSize: 50 }, signal)
  const params = new URL('http://localhost' + request.mock.calls[0][0]).searchParams
  expect(JSON.parse(Buffer.from(params.get('filter')!, 'base64url').toString('utf8'))).toEqual(filter)
  expect(JSON.parse(Buffer.from(params.get('orderBy')!, 'base64url').toString('utf8'))).toEqual(orderBy)
  expect(params.get('page')).toBe('3'); expect(request.mock.calls[0][1]).toEqual({ signal })
})

it('recovers record creation without generating another operation identity', async () => {
  const request = vi.fn().mockRejectedValueOnce(new TypeError('offline')).mockResolvedValueOnce(operation)
  await expect(api(request).create({ values: [] }, 'key')).resolves.toEqual(record)
  expect(request).toHaveBeenCalledTimes(2)
  expect(request.mock.calls[0][1].body.datasetGeneration).toBe('g')
})

it.each([
  { key: { type: 'text' as const, value: '001 / 😀' }, encoded: '001 / 😀' },
  { key: { type: 'text' as const, value: '1' }, encoded: '1' },
  { key: { type: 'integer' as const, value: '1' }, encoded: '1' },
])('deletes the exact typed record identity $key.type:$key.value', async ({ key, encoded }) => {
  const exactRef = { ...scope, recordKey: key }
  const result = { target: { type: 'record' as const, recordRef: exactRef }, deleted: true as const }
  const op = { ...deleteOperation, resource: { type: 'record' as const, recordRef: exactRef }, result }
  const request = vi.fn().mockResolvedValueOnce({ operation: op }).mockResolvedValueOnce(op)
  const records = api(request)
  const body = { expectedContentRevision: 1, expectedStatusRevision: 2, expectedLinkRevision: 3, impactRevision: 4 }
  await expect(records.delete(key, body, 'key')).resolves.toEqual(result)
  await expect(records.delete(key, body, 'key', true, { lookupOnly: true })).resolves.toEqual(result)
  const [url, init] = request.mock.calls[0]
  expect(Buffer.from(String(url).split('/records/')[1], 'base64url').toString('utf8')).toBe(encoded)
  expect(init).toEqual({ method: 'DELETE', headers: { 'Idempotency-Key': 'key' }, body: { ...body, datasetGeneration: 'g', recordKeyType: key.type } })
  expect(request).toHaveBeenCalledTimes(2)
})

it.each([
  { ...deleteOperation, resource: { type: 'record', recordRef: { ...ref, projectId: 'other' } } },
  { ...deleteOperation, resource: { type: 'record', recordRef: { ...ref, tableId: 'other' } } },
  { ...deleteOperation, resource: { type: 'record', recordRef: { ...ref, datasetGeneration: 'old' } } },
  { ...deleteOperation, resource: { type: 'record', recordRef: { ...ref, recordKey: { type: 'integer', value: '1' } } } },
  { ...deleteOperation, result: { ...deleted, deleted: false } },
  { ...deleteOperation, result: { ...deleted, target: { type: 'record', recordRef: { ...ref, projectId: 'other' } } } },
  { ...deleteOperation, result: { ...deleted, target: { type: 'record', recordRef: { ...ref, tableId: 'other' } } } },
  { ...deleteOperation, result: { ...deleted, target: { type: 'record', recordRef: { ...ref, datasetGeneration: 'old' } } } },
  { ...deleteOperation, result: { ...deleted, target: { type: 'record', recordRef: { ...ref, recordKey: { type: 'integer', value: '1' } } } } },
])('rejects mismatched record deletion without resending', async wrong => {
  const request = vi.fn().mockResolvedValueOnce(wrong)
  await expect(api(request).delete(ref.recordKey, { expectedContentRevision: 1, expectedStatusRevision: 2, expectedLinkRevision: 3, impactRevision: 4 }, 'key', true)).rejects.toBeInstanceOf(DataCommandUncertain)
  expect(request).toHaveBeenCalledTimes(1)
})

it.each([
  { ...operation, projectId: 'other' },
  { ...operation, kind: 'updateRecord' },
  { ...operation, resource: { type: 'record', recordRef: { ...ref, datasetGeneration: 'old' } } },
  { ...operation, result: { ...record, ref: { ...ref, tableId: 'other' } } },
  { ...operation, result: { ...record, ref: { ...ref, recordKey: { type: 'integer', value: '1' } } } },
])('rejects a mismatched operation without resending', async wrong => {
  const request = vi.fn().mockResolvedValueOnce(wrong)
  await expect(api(request).create({ values: [] }, 'key', true)).rejects.toBeInstanceOf(DataCommandUncertain)
  expect(request).toHaveBeenCalledTimes(1)
})

it('distinguishes text and integer targets in recovered edits', async () => {
  const request = vi.fn().mockResolvedValueOnce({ ...operation, kind: 'updateRecord' })
  await expect(api(request).update({ type: 'integer', value: '1' }, { values: [], expectedContentRevision: 1 }, 'key', true)).rejects.toBeInstanceOf(DataCommandUncertain)
})

it('sends explicit null status and optional from-status only when supplied', async () => {
  const request = vi.fn().mockResolvedValue(record)
  const records = api(request)
  await records.setStatus(ref.recordKey, { statusId: null, expectedStatusRevision: 1 }, 'key')
  await records.setStatus(ref.recordKey, { statusId: null, expectedStatusRevision: 1, expectedFromStatusId: null }, 'key2')
  expect(request.mock.calls[0][1].body).not.toHaveProperty('expectedFromStatusId')
  expect(request.mock.calls[1][1].body).toHaveProperty('expectedFromStatusId', null)
  expect(request.mock.calls[0][1].method).toBe('PUT')
})

it('previews record deletion without an idempotency key', async () => {
  const request = vi.fn().mockResolvedValueOnce({})
  const signal = new AbortController().signal
  await api(request).previewDelete(ref.recordKey, signal)
  expect(request).toHaveBeenCalledWith('/api/v1/projects/p/mutation-impact', { method: 'POST', signal, body: { action: 'deleteRecord', target: { type: 'record', recordRef: ref } } })
  expect(request.mock.calls[0][1]).not.toHaveProperty('headers')
})

it('passes a dynamic submit guard through every existing record write', async () => {
  const request = vi.fn().mockRejectedValue(new ApiClientError('absent', 404, 'OPERATION_NOT_FOUND'))
  const canSubmit = vi.fn(() => false)
  const records = api(request)
  const calls = [
    records.create({ values: [] }, 'key', true, { canSubmit }),
    records.update(ref.recordKey, { values: [], expectedContentRevision: 1 }, 'key', true, { canSubmit }),
    records.setStatus(ref.recordKey, { statusId: null, expectedStatusRevision: 1 }, 'key', true, { canSubmit }),
  ]
  await Promise.all(calls.map(call => expect(call).rejects.toBeInstanceOf(DataCommandUncertain)))
  expect(canSubmit).toHaveBeenCalledTimes(3)
})

it('only resends the original body after operation-not-found', async () => {
  const body = { values: [{ fieldId: 'f', value: 'original' }] }
  const request = vi.fn().mockImplementationOnce(async () => { body.values[0].value = 'draft'; throw new TypeError('offline') })
    .mockRejectedValueOnce(new ApiClientError('missing', 404, 'OPERATION_NOT_FOUND')).mockResolvedValueOnce(record)
  await expect(api(request).create(body, 'key')).resolves.toEqual(record)
  expect(request.mock.calls[2]).toEqual(request.mock.calls[0])
  expect(request.mock.calls[2][1].body.values[0].value).toBe('original')
})

it('rejects a lone surrogate instead of silently replacing record identity', () => {
  const request = vi.fn()
  expect(() => api(request).get({ type: 'text', value: '\ud800' })).toThrow('Unicode')
  expect(request).not.toHaveBeenCalled()
})

it.each([NaN, Infinity, -Infinity])('never serializes non-finite %s into a null write', async value => {
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(record), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetcher)
  try {
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:9999', token: 'test', timeoutMs: 0 })
    await expect(createRecordsApi(client, scope).update(ref.recordKey, { values: [{ fieldId: 'number-field', value }], expectedContentRevision: 1 }, 'key')).rejects.toThrow()
    expect(fetcher).not.toHaveBeenCalled()
  } finally { vi.unstubAllGlobals() }
})
