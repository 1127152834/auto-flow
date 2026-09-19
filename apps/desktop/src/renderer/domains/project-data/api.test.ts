import { expect, it, vi } from 'vitest'
import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import { createProjectDataApi, DataCommandUncertain } from './api'

function client(request: StreamingApiClient['request']): StreamingApiClient {
  return { request, health: vi.fn(), stream: vi.fn() }
}
const table = { projectId: 'p', tableId: 't', name: 'Data', tableRevision: 1, sourceKind: 'local' as const }
const operation = {
  projectId: 'p', idempotencyKey: 'key', kind: 'createTable', status: 'succeeded',
  resource: { type: 'table', projectId: 'p', tableId: 't' }, result: table,
}

it('recovers a lost creation response using its original operation identity', async () => {
  const request = vi.fn().mockRejectedValueOnce(new TypeError('network')).mockResolvedValueOnce(operation)
  await expect(createProjectDataApi(client(request), 'p').create({ name: 'Data', description: '' }, 'key')).resolves.toEqual(table)
  expect(request.mock.calls[1][0]).toBe('/api/v1/projects/p/operations/by-idempotency-key/key')
  expect(request).toHaveBeenCalledTimes(2)
})

it('only resends after the original operation is confirmed absent', async () => {
  const request = vi.fn().mockRejectedValueOnce(new TypeError('network'))
    .mockRejectedValueOnce(new ApiClientError('absent', 404, 'OPERATION_NOT_FOUND'))
    .mockResolvedValueOnce(table)
  await expect(createProjectDataApi(client(request), 'p').create({ name: 'Data', description: '' }, 'key')).resolves.toEqual(table)
  expect(request.mock.calls[2]).toEqual(request.mock.calls[0])
})

it.each([
  { ...operation, resource: { type: 'table', projectId: 'other', tableId: 't' } },
  { ...operation, idempotencyKey: 'other-key' },
  { ...operation, kind: 'updateTable' },
  { ...operation, result: { projectId: 'p', name: 'Project', managementRevision: 1 } },
])('keeps the draft uncertain when a lookup returns a different command', async (wrong) => {
  const request = vi.fn().mockResolvedValueOnce(wrong)
  await expect(createProjectDataApi(client(request), 'p').resumeCreate({ name: 'Data', description: '' }, 'key')).rejects.toBeInstanceOf(DataCommandUncertain)
  expect(request).toHaveBeenCalledTimes(1)
})

it('does not retry revision conflicts and retains the original failure facts', async () => {
  const conflict = new ApiClientError('changed', 409, 'REVISION_CONFLICT')
  const request = vi.fn().mockRejectedValueOnce(conflict)
  await expect(createProjectDataApi(client(request), 'p').patch('t', { name: 'Edit', expectedTableRevision: 1 }, 'key')).rejects.toBe(conflict)
  expect(request).toHaveBeenCalledTimes(1)
})

it('passes cancellation and URL encoded directory conditions', async () => {
  const request = vi.fn().mockResolvedValue({ items: [], total: 0 })
  const signal = new AbortController().signal
  await createProjectDataApi(client(request), 'p').list({ query: 'a&b', page: 2, pageSize: 50, sort: 'name' }, signal)
  expect(request).toHaveBeenCalledWith('/api/v1/projects/p/tables?q=a%26b&page=2&pageSize=50&sort=name', { signal })
})

it('freezes table command values before a failed request and retry', async () => {
  const body = { name: 'Original', description: '' }
  const request = vi.fn().mockImplementationOnce(async () => { body.name = 'Later draft'; throw new TypeError('network') })
    .mockRejectedValueOnce(new ApiClientError('absent', 404, 'OPERATION_NOT_FOUND')).mockResolvedValueOnce(table)
  await createProjectDataApi(client(request), 'p').create(body, 'key')
  expect(request.mock.calls[2][1].body.name).toBe('Original')
})
it('checks the operation project as well as its resource and result', async () => {
  const request = vi.fn().mockResolvedValueOnce({ ...operation, projectId: 'other' })
  await expect(createProjectDataApi(client(request), 'p').resumeCreate({ name: 'Data', description: '' }, 'key')).rejects.toBeInstanceOf(DataCommandUncertain)
  expect(request).toHaveBeenCalledOnce()
})
it('rejects a recovered table edit belonging to another target', async () => {
  const request = vi.fn().mockResolvedValueOnce({ ...operation, kind: 'updateTable' })
  await expect(createProjectDataApi(client(request), 'p').resumePatch('other', { name: 'Edit', expectedTableRevision: 1 }, 'key')).rejects.toBeInstanceOf(DataCommandUncertain)
  expect(request).toHaveBeenCalledOnce()
})
