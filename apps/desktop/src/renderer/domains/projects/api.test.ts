import { describe, expect, it, vi } from 'vitest'
import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import { createProjectsApi, isDefinitiveProjectFailure, ProjectCommandUncertain } from './api'

function client(request: StreamingApiClient['request']): StreamingApiClient {
  return { request, health: vi.fn(), stream: vi.fn() }
}

describe('createProjectsApi', () => {
  const operation = (result: object) => ({ status: 'succeeded', kind: 'createProject', resource: { type: 'project' }, result })
  it('passes AbortSignal and encoded list conditions', async () => {
    const request = vi.fn().mockResolvedValue({ items: [], total: 0, offset: 50, limit: 50 })
    const api = createProjectsApi(client(request))
    const signal = new AbortController().signal
    await api.list({ query: 'A&B', lifecycle: 'active', sort: 'name', page: 2, pageSize: 50 }, signal)
    expect(request).toHaveBeenCalledWith('/api/v1/projects?q=A%26B&lifecycleState=active&sort=name&page=2&pageSize=50', { signal })
  })

  it('creates with one idempotency key and recovers an unknown response by key', async () => {
    const created = { projectId: 'p1', name: '项目', managementRevision: 1 }
    const request = vi.fn()
      .mockRejectedValueOnce(new ApiClientError('结果未知', 503, { code: 'UNKNOWN', message: '结果未知', request_id: 'r', field_errors: {}, retry_after_seconds: null, outcome_unknown: true }))
      .mockResolvedValueOnce(operation(created))
    const api = createProjectsApi(client(request), () => 'fixed-key')
    await expect(api.create({ name: '项目', description: '' })).resolves.toEqual(created)
    expect(request).toHaveBeenNthCalledWith(1, '/api/v1/projects', expect.objectContaining({ method: 'POST', headers: { 'Idempotency-Key': 'fixed-key' } }))
    expect(request).toHaveBeenNthCalledWith(2, '/api/v1/workspace/operations/by-idempotency-key/fixed-key')
    expect(request).toHaveBeenCalledTimes(2)
  })

  it('retries the original create once only when key lookup returns 404', async () => {
    const created = { projectId: 'p1', name: '项目', managementRevision: 1 }
    const unknown = new ApiClientError('结果未知', 503, { code: 'UNKNOWN', message: '结果未知', request_id: 'r', field_errors: {}, retry_after_seconds: null, outcome_unknown: true })
    const request = vi.fn().mockRejectedValueOnce(unknown).mockRejectedValueOnce(new ApiClientError('missing', 404, 'OPERATION_NOT_FOUND')).mockResolvedValueOnce(created)
    const api = createProjectsApi(client(request), () => 'fixed-key')
    await expect(api.create({ name: '项目', description: '' })).resolves.toEqual(created)
    expect(request.mock.calls[2]?.[1]).toMatchObject({ method: 'POST', headers: { 'Idempotency-Key': 'fixed-key' }, body: { name: '项目', description: '' } })
  })

  it('keeps the command key when both submission and lookup lose their connections', async () => {
    const created = { projectId: 'p1', name: '项目', managementRevision: 1 }
    const request = vi.fn().mockRejectedValueOnce(new TypeError('network')).mockRejectedValueOnce(new TypeError('network')).mockResolvedValueOnce(operation(created))
    const api = createProjectsApi(client(request), () => 'fixed-key')
    await expect(api.create({ name: '项目', description: '' }, 'fixed-key')).rejects.toBeInstanceOf(ProjectCommandUncertain)
    await expect(api.resumeCreate({ name: '项目', description: '' }, 'fixed-key')).resolves.toEqual(created)
    expect(request).toHaveBeenNthCalledWith(3, '/api/v1/workspace/operations/by-idempotency-key/fixed-key')
    expect(request.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  })

  it('marks the command uncertain when a timed out submit is followed by lookup 401', async () => {
    const request = vi.fn()
      .mockRejectedValueOnce(new DOMException('timeout', 'TimeoutError'))
      .mockRejectedValueOnce(new ApiClientError('unauthorized', 401, 'UNAUTHORIZED'))
    const api = createProjectsApi(client(request), () => 'fixed-key')
    await expect(api.create({ name: '项目', description: '' })).rejects.toBeInstanceOf(ProjectCommandUncertain)
    expect(request).toHaveBeenCalledTimes(2)
  })

  it('does not query after a definitive validation failure', async () => {
    const error = new ApiClientError('invalid', 422, 'VALIDATION_ERROR')
    const request = vi.fn().mockRejectedValue(error)
    const api = createProjectsApi(client(request), () => 'fixed-key')
    await expect(api.create({ name: '项目', description: '' })).rejects.toBe(error)
    expect(request).toHaveBeenCalledTimes(1)
    expect(isDefinitiveProjectFailure(error)).toBe(true)
    expect(isDefinitiveProjectFailure(new ApiClientError('timeout', 408))).toBe(false)
  })

  it('keeps the uncertainty marker when the retry also loses its response', async () => {
    const request = vi.fn()
      .mockRejectedValueOnce(new TypeError('first network loss'))
      .mockRejectedValueOnce(new ApiClientError('missing', 404, 'OPERATION_NOT_FOUND'))
      .mockRejectedValueOnce(new SyntaxError('invalid response json'))
    const api = createProjectsApi(client(request), () => 'fixed-key')
    await expect(api.create({ name: '项目', description: '' })).rejects.toBeInstanceOf(ProjectCommandUncertain)
    expect(request).toHaveBeenCalledTimes(3)
  })

  it('does not retry an arbitrary lookup 404', async () => {
    const request = vi.fn()
      .mockRejectedValueOnce(new TypeError('network'))
      .mockRejectedValueOnce(new ApiClientError('route missing', 404, 'RESOURCE_NOT_FOUND'))
    const api = createProjectsApi(client(request), () => 'fixed-key')
    await expect(api.create({ name: '项目', description: '' })).rejects.toBeInstanceOf(ProjectCommandUncertain)
    expect(request).toHaveBeenCalledTimes(2)
  })
})


it('does not treat a recovered data table operation as a saved project', async () => {
  const request = vi.fn().mockResolvedValue({
    status: 'succeeded', kind: 'createTable', resource: { type: 'table', projectId: 'p1', tableId: 't1' },
    result: { projectId: 'p1', tableId: 't1', name: 'table', tableRevision: 1 },
  })
  const api = createProjectsApi(client(request))
  await expect(api.resumeCreate({ name: 'project', description: '' }, 'key')).rejects.toBeInstanceOf(ProjectCommandUncertain)
  expect(request).toHaveBeenCalledTimes(1)
})
