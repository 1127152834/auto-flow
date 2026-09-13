import { expect, it, vi } from 'vitest'
import { createSchemaApi } from './schema-api'
import { DataCommandUncertain } from './data-command'
import { ApiClientError } from '../../shared/api/client'

const scope = { projectId: 'p', tableId: 't', datasetGeneration: 'g' }
const candidate = { datasetGeneration: 'g', expectedTableRevision: 1, fields: [] }
const body = { candidate, impactRevision: 1 }
const result = { action: 'saveSchema', datasetGeneration: 'g', tableRevision: 1, fields: [], createdFieldIds: {}, backfilledRecords: 0 }
const operation = { projectId: 'p', idempotencyKey: 'k', kind: 'saveTableSchema', status: 'succeeded', resource: { type: 'table', ...scope }, result }
const setup = (request = vi.fn()) => ({ request, api: createSchemaApi({ request, health: vi.fn(), stream: vi.fn() }, scope) })

it('previews a candidate with abort support and recovers only the original committed operation', async () => {
  const { request, api } = setup(vi.fn().mockResolvedValueOnce({}).mockRejectedValueOnce(new TypeError('lost')).mockResolvedValueOnce(operation))
  const signal = new AbortController().signal
  await api.preview(candidate, signal)
  expect(request.mock.calls[0]).toEqual(['/api/v1/projects/p/tables/t/schema/preview', { method: 'POST', body: candidate, signal }])
  await expect(api.commit(body, 'k')).resolves.toEqual(result)
  expect(request.mock.calls[2][0]).toBe('/api/v1/projects/p/operations/by-idempotency-key/k')
  expect(request).toHaveBeenCalledTimes(3)
})

it.each([
  { ...operation, resource: { ...operation.resource, projectId: 'other' } },
  { ...operation, resource: { ...operation.resource, tableId: 'other' } },
  { ...operation, result: { ...result, datasetGeneration: 'old' } },
  { ...operation, kind: 'mutateField' },
  { ...operation, result: { ...result, action: 'create' } },
  { ...operation, result: { ...result, tableRevision: 0 } },
  { ...operation, result: { ...result, fields: [{ ref: { ...scope, tableId: 'other', fieldId: 'f' } }] } },
])('rejects mismatched recovery without sending a second save', async wrong => {
  const { request, api } = setup(vi.fn().mockResolvedValueOnce(wrong))
  await expect(api.commit(body, 'k', true, { lookupOnly: true })).rejects.toBeInstanceOf(DataCommandUncertain)
  expect(request).toHaveBeenCalledTimes(1)
})

it('preserves definitive conflicts and does not query or recreate an operation', async () => {
  const error = new ApiClientError('changed', 409, 'REVISION_CONFLICT')
  const { request, api } = setup(vi.fn().mockRejectedValue(error))
  await expect(api.commit(body, 'k')).rejects.toBe(error)
  expect(request).toHaveBeenCalledTimes(1)
})
