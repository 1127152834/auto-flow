import { describe, expect, it, vi } from 'vitest'
import type { StreamingApiClient } from '../../shared/api/client'
import { ApiClientError } from '../../shared/api/client'
import { createSheetsApi } from './sheets-api'

const operation = (kind: string, extra: Record<string, unknown> = {}) => ({
  operationId: 'op', projectId: 'p', idempotencyKey: 'key', kind,
  status: 'succeeded', resource: { type: 'project', projectId: 'p' }, result: null,
  operationRevision: 1, error: null, createdAt: '', updatedAt: '', ...extra,
})

function setup() {
  const request = vi.fn()
  const desktop = { connectGoogleSheets: vi.fn() }
  const api = createSheetsApi({ request } as unknown as StreamingApiClient, desktop, 'p')
  return { request, desktop, api }
}

describe('Sheets command transport', () => {
  it('submits a connection under the renderer key and refuses a foreign operation kind', async () => {
    const { api, request } = setup()
    request.mockResolvedValue({ operation: operation('connectSheets') })
    expect((await api.connect('运营', 'token', 'key', () => true)).kind).toBe('connectSheets')
    expect(request).toHaveBeenCalledWith('/api/v1/projects/p/sheets/connections', expect.objectContaining({ method: 'POST', headers: { 'Idempotency-Key': 'key' }, body: { accountLabel: '运营', authorizationToken: 'token' } }))
  })

  it('rejects a response whose kind is not the submitted sheets command', async () => {
    const { api, request } = setup()
    request.mockResolvedValue({ operation: operation('updateRecord') })
    await expect(api.putBinding('t', {} as never, 'key', () => true)).rejects.toThrow('操作结果与当前请求不一致')
  })

  it('publishes a binding with PUT, the verb the binding resource froze', async () => {
    const { api, request } = setup()
    request.mockResolvedValue({ operation: operation('changeSheetsBinding') })
    await api.putBinding('t', { impactRevision: 1 } as never, 'key', () => true)
    expect(request).toHaveBeenCalledWith('/api/v1/projects/p/tables/t/sheets/binding', expect.objectContaining({ method: 'PUT', headers: { 'Idempotency-Key': 'key' } }))
  })

  it('recovers a lost push response by the original key instead of sending a second command', async () => {
    const { api, request } = setup()
    request.mockRejectedValueOnce(new TypeError('lost response'))
    request.mockResolvedValueOnce(operation('syncPush', { status: 'unknown' }))
    const result = await api.push('t', 'due', 3, 'key', () => true)
    expect(result.status).toBe('unknown')
    expect(request).toHaveBeenLastCalledWith('/api/v1/projects/p/operations/by-idempotency-key/key', undefined)
    expect(request).toHaveBeenCalledTimes(2)
  })

  it('keeps an unaccepted command uncertain rather than opening a new identity', async () => {
    const { api, request } = setup()
    request.mockRejectedValueOnce(new TypeError('lost'))
    request.mockRejectedValueOnce(new ApiClientError('missing', 404, 'OPERATION_NOT_FOUND'))
    await expect(api.push('t', 'due', 3, 'key', () => true)).rejects.toThrow('原操作尚未接受')
    expect(request).toHaveBeenCalledTimes(2)
  })

  it('reads the inspection off the accepted operation so a lost response stays recoverable', async () => {
    const { api, request } = setup()
    const inspection = { valid: true, issues: [], columns: [], identitySummary: { unique: true, missing: 0, duplicates: 0 }, overlaps: [] }
    request.mockResolvedValue({ operation: operation('inspectSheets', { result: { inspection } }) })
    const outcome = await api.inspect('t', { connectionId: 'c', spreadsheetId: 's', sheetId: 0, identityStrategy: { kind: 'column', columnId: 'A' }, mapping: [] }, 'key', () => true)
    expect(outcome.inspection).toEqual(inspection)
  })

  it('never sends a Google credential from the renderer and treats a cancelled handshake as a normal outcome', async () => {
    const { api, desktop, request } = setup()
    desktop.connectGoogleSheets.mockResolvedValue({ ok: true, value: null })
    expect(await api.authorize('运营')).toBeNull()
    expect(request).not.toHaveBeenCalled()
  })

  it('surfaces a desktop handshake failure without inventing a connection', async () => {
    const { api, desktop, request } = setup()
    desktop.connectGoogleSheets.mockResolvedValue({ ok: false, error: { code: 'GOOGLE_AUTH_DENIED', message: '授权被拒绝' } })
    await expect(api.authorize('运营')).rejects.toThrow('授权被拒绝')
    expect(request).not.toHaveBeenCalled()
  })

  it('carries the binding epoch on pause so a stale view cannot pause a new binding', async () => {
    const { api, request } = setup()
    request.mockResolvedValue({ summary: { status: 'paused', pendingCount: 0, unknownCount: 0 }, binding: null })
    await api.pause('t', 4)
    expect(request).toHaveBeenCalledWith('/api/v1/projects/p/tables/t/sync/pause', expect.objectContaining({ method: 'POST', body: { expectedBindingEpoch: 4 } }))
  })
})
