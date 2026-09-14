import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiClientError, type ApiRequestInit, type StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'
import { useDataTableEditing, type EditingContext } from './use-data-table-editing'

type Schema = components['schemas']
const scope = { workspaceKey: 'w', projectId: 'p', tableId: 't', datasetGeneration: 'g' }
const table: Schema['DataTableView'] = { projectId: 'p', tableId: 't', name: 'T', description: '', sourceKind: 'local', datasetGeneration: 'g', tableRevision: 1, identity: { mode: 'system' }, slotDefinitions: [], recordCount: 1, syncSummary: { status: 'idle', pendingCount: 0, unknownCount: 0 }, createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T00:00:00Z' }
const field: Schema['DataFieldView'] = { key: 'name', name: 'Name', type: 'string', required: false, validation: {}, ref: { projectId: 'p', tableId: 't', datasetGeneration: 'g', fieldId: 'f' }, writable: true, formula: false, fieldRevision: 2 }
const status: Schema['DataStatusView'] = { statusId: 's', name: 'Ready', color: '#112233', order: 0, statusRevision: 3 }
const record: Schema['DataRecordView'] = { ref: { projectId: 'p', tableId: 't', datasetGeneration: 'g', recordKey: { type: 'text', value: 'r' } }, values: [{ fieldId: 'f', value: 'old', source: 'local', readable: true }], recordSlots: [], statusId: null, currentEnvironmentId: null, contentRevision: 1, statusRevision: 4, linkRevision: 5, deleted: false, createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T00:00:00Z' }
const context = (overrides: Partial<EditingContext> = {}): EditingContext => ({ scope, table, fields: { items: [field], tableRevision: 6 }, statuses: { items: [status], tableRevision: 7 }, ...overrides })
const schemaCandidate: Schema['DataSchemaCandidate'] = { datasetGeneration: 'g', expectedTableRevision: 6, fields: [{ kind: 'existing', fieldId: 'f', expectedFieldRevision: 2, definition: { key: 'name', name: 'Renamed', type: 'string', required: false, validation: {} } }] }
const schemaImpact: Schema['DataSchemaImpact'] = { impactRevision: 12, calculatedAt: '2026-01-01T00:00:00Z', expiresAt: '2026-01-01T00:05:00Z', affectedRecords: 1, backfillBytes: 0, blockers: [], warnings: [], referenceAvailability: { automations: 'notImplemented', sync: 'notImplemented' } }
const client = (request: (path: string, init?: ApiRequestInit) => Promise<unknown>): StreamingApiClient => ({ request, health: vi.fn(), stream: vi.fn() }) as StreamingApiClient
beforeEach(() => {
  const values = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    get length() { return values.size },
    clear: () => values.clear(),
    getItem: (key: string) => values.get(key) ?? null,
    key: (index: number) => [...values.keys()][index] ?? null,
    removeItem: (key: string) => values.delete(key),
    setItem: (key: string, value: string) => values.set(key, value),
  })
})
afterEach(() => vi.unstubAllGlobals())

it('previews and persists the exact schema candidate through the shared command engine', async () => {
  let finish!: (value: unknown) => void
  const request = vi.fn((path: string, _init?: ApiRequestInit) => path.endsWith('/preview') ? Promise.resolve(schemaImpact) : new Promise(resolve => { finish = resolve }))
  const props = { workspaceKey: 'w', context: context(), client: client(request), instanceId: 'i', disabled: false, readonly: false, onSaved: vi.fn() }
  const { result } = renderHook(() => useDataTableEditing(props))
  act(() => result.current.open({ kind: 'schemaSave' }))
  await act(async () => { expect(await result.current.previewSchema(schemaCandidate)).toEqual(schemaImpact) })
  let saving!: Promise<unknown>
  act(() => { saving = result.current.submitSchema({ candidate: schemaCandidate, impactRevision: 12 }) })
  expect(request.mock.calls[1][1]?.body).toEqual({ candidate: schemaCandidate, impactRevision: 12 })
  expect(result.current.canLeave()).toBe(false)
  await expect(result.current.submitSchema({ candidate: schemaCandidate, impactRevision: 12 })).rejects.toThrow()
  const key = (request.mock.calls[1][1]?.headers as Record<string,string>)['Idempotency-Key']
  await act(async () => { finish({ action: 'saveSchema', datasetGeneration: 'g', tableRevision: 7, fields: [{ ...field, name: 'Renamed', fieldRevision: 3 }] }); await saving })
  expect(props.onSaved).toHaveBeenCalledWith('schemaSave', key, expect.objectContaining({ action: 'saveSchema' }))
})

it('binds schema preview to the editor generation, baseline revision, and exact candidate', async () => {
  const request = vi.fn().mockResolvedValue(schemaImpact)
  const props = { workspaceKey: 'w', context: context(), client: client(request), instanceId: 'i', disabled: false, readonly: false, onSaved: vi.fn() }
  const { result, rerender } = renderHook(p => useDataTableEditing(p), { initialProps: props })
  act(() => result.current.open({ kind: 'schemaSave' }))
  await expect(result.current.previewSchema({ ...schemaCandidate, datasetGeneration: 'other' })).rejects.toThrow('资料已变化')
  expect(request).not.toHaveBeenCalled()
  await act(async () => { await result.current.previewSchema(schemaCandidate) })
  await expect(result.current.submitSchema({ candidate: { ...schemaCandidate, fields: [] }, impactRevision: 12 })).rejects.toThrow('尚未通过预检')
  rerender({ ...props, readonly: true })
  await expect(result.current.previewSchema(schemaCandidate)).rejects.toThrow('不可写')
  expect(request).toHaveBeenCalledTimes(1)
})

it('restores a schema candidate after a lost response and only looks up the original key', async () => {
  const offline = vi.fn((path: string, _init?: ApiRequestInit) => path.endsWith('/preview') ? Promise.resolve(schemaImpact) : Promise.reject(new TypeError('offline')))
  const props = { workspaceKey: 'w', context: context(), client: client(offline), instanceId: 'i1', disabled: false, readonly: false, onSaved: vi.fn() }
  const first = renderHook(() => useDataTableEditing(props))
  act(() => first.result.current.open({ kind: 'schemaSave' }))
  await act(async () => { await first.result.current.previewSchema(schemaCandidate) })
  await expect(first.result.current.submitSchema({ candidate: schemaCandidate, impactRevision: 12 })).rejects.toThrow()
  const key = (offline.mock.calls[1][1]?.headers as Record<string,string>)['Idempotency-Key']
  first.unmount()
  const lookup = vi.fn().mockResolvedValue({ projectId: 'p', idempotencyKey: key, kind: 'saveTableSchema', status: 'succeeded', resource: { type: 'table', projectId: 'p', tableId: 't' }, result: { action: 'saveSchema', datasetGeneration: 'g', tableRevision: 7, fields: [{ ...field, name: 'Renamed', fieldRevision: 3 }] } })
  const restored = renderHook(() => useDataTableEditing({ ...props, client: client(lookup), instanceId: 'i2' }))
  expect(restored.result.current.editor).toMatchObject({ kind: 'schemaSave', submittedSchema: schemaCandidate })
  expect(restored.result.current.recoveryPending).toBe(true)
  await act(async () => { await restored.result.current.recover() })
  expect(lookup.mock.calls.map(call => call[0])).toEqual([`/api/v1/projects/p/operations/by-idempotency-key/${key}`])
})

it('freezes record and directory revisions and blocks a duplicate submit synchronously', async () => {
  let resolve!: (value: unknown) => void
  const request = vi.fn((_path: string, _init?: ApiRequestInit) => new Promise(value => { resolve = value }))
  const props = { workspaceKey: 'w', context: context(), client: client(request), instanceId: 'i', disabled: false, readonly: false, onSaved: vi.fn() }
  const { result, rerender } = renderHook(p => useDataTableEditing(p), { initialProps: props })
  act(() => result.current.open({ kind: 'recordEdit', record }))
  rerender({ ...props, context: context({ fields: { items: [{ ...field, fieldRevision: 9 }], tableRevision: 9 } }) })
  let first!: Promise<unknown>, second!: Promise<unknown>
  act(() => { first = result.current.submitRecord([{ fieldId: 'f', value: 'new' }]); second = result.current.submitRecord([{ fieldId: 'f', value: 'other' }]) })
  expect(request).toHaveBeenCalledTimes(1)
  expect(request.mock.calls[0][1]?.body).toMatchObject({ values: [{ fieldId: 'f', value: 'new' }], expectedContentRevision: 1, datasetGeneration: 'g' })
  await expect(second).rejects.toThrow()
  await act(async () => { resolve(record); await first })
})

it('invalidates a late success after instance change and recovers only by lookup with the original key', async () => {
  let reject!: (error: unknown) => void
  const first = vi.fn((path: string, _init?: ApiRequestInit) => path.includes('/operations/')
    ? Promise.reject(new ApiClientError('absent', 404, 'OPERATION_NOT_FOUND'))
    : new Promise((_resolve, rejectPromise) => { reject = rejectPromise }))
  const onSaved = vi.fn()
  const initial = { workspaceKey: 'w', context: context(), client: client(first), instanceId: 'i1', disabled: false, readonly: false, onSaved }
  const { result, rerender } = renderHook(p => useDataTableEditing(p), { initialProps: initial })
  act(() => result.current.open({ kind: 'recordCreate' }))
  let submission!: Promise<unknown>
  act(() => { submission = result.current.submitRecord([]) })
  const key = (first.mock.calls[0][1]?.headers as Record<string, string>)['Idempotency-Key']
  const lookup = vi.fn().mockResolvedValue({ projectId: 'p', idempotencyKey: key, kind: 'createRecord', status: 'succeeded', resource: { type: 'record', recordRef: record.ref }, result: record })
  rerender({ ...initial, client: client(lookup), instanceId: 'i2' })
  await act(async () => { reject(new TypeError('offline')); await submission })
  expect(onSaved).not.toHaveBeenCalled()
  await act(async () => { await result.current.recover() })
  expect(lookup.mock.calls.map(call => call[0])).toEqual([`/api/v1/projects/p/operations/by-idempotency-key/${key}`])
  expect(onSaved).toHaveBeenCalledWith('recordCreate', key, record)
})

it('keeps an absent command frozen in readonly mode without resubmitting it', async () => {
  const initialRequest = vi.fn().mockRejectedValue(new TypeError('offline'))
  const props = { workspaceKey: 'w', context: context(), client: client(initialRequest), instanceId: 'i', disabled: false, readonly: false, onSaved: vi.fn() }
  const { result, rerender } = renderHook(p => useDataTableEditing(p), { initialProps: props })
  act(() => result.current.open({ kind: 'recordCreate' }))
  await expect(result.current.submitRecord([])).rejects.toThrow()
  const request = vi.fn().mockRejectedValue(new ApiClientError('absent', 404, 'OPERATION_NOT_FOUND'))
  rerender({ ...props, client: client(request), instanceId: 'i2', readonly: true })
  await expect(result.current.recover()).rejects.toThrow()
  expect(request).toHaveBeenCalledTimes(1)
  expect(request.mock.calls[0][0]).toContain('/operations/by-idempotency-key/')
})

describe('frozen payloads', () => {
  it('sends only changed table values with the frozen table revision and recovers by the original key', async () => {
    const updated = { ...table, name: 'Renamed', tableRevision: 2 }
    const request = vi.fn().mockResolvedValue(updated)
    const props = { workspaceKey: 'w', context: context(), client: client(request), instanceId: 'i', disabled: false, readonly: false, onSaved: vi.fn() }
    const { result } = renderHook(() => useDataTableEditing(props))
    act(() => result.current.open({ kind: 'tableEdit' }))
    await act(async () => { await result.current.submitTable({ name: 'Renamed', description: table.description }) })
    expect(request.mock.calls[0][1]?.body).toEqual({ name: 'Renamed', expectedTableRevision: 1 })

    act(() => result.current.open({ kind: 'tableEdit' }))
    await expect(result.current.submitTable({ name: table.name, description: table.description })).rejects.toThrow('数据表没有修改')
    expect(request).toHaveBeenCalledTimes(1)
  })

  it('sends the exact bodies for record create, edit, and status including null', async () => {
    const request = vi.fn().mockResolvedValue(record)
    const props = { workspaceKey: 'w', context: context(), client: client(request), instanceId: 'i', disabled: false, readonly: false, onSaved: vi.fn() }
    const { result } = renderHook(() => useDataTableEditing(props))
    act(() => result.current.open({ kind: 'recordCreate' })); await act(async () => { await result.current.submitRecord([]) })
    expect(request.mock.calls[0][1]?.body).toEqual({ values: [], datasetGeneration: 'g' })
    act(() => result.current.open({ kind: 'recordEdit', record })); await act(async () => { await result.current.submitRecord([{ fieldId: 'f', value: null }]) })
    expect(request.mock.calls[1][1]?.body).toEqual({ values: [{ fieldId: 'f', value: null }], expectedContentRevision: 1, datasetGeneration: 'g', recordKeyType: 'text' })
    act(() => result.current.open({ kind: 'recordStatus', record })); await act(async () => { await result.current.submitRecordStatus('s') })
    expect(request.mock.calls[2][1]?.body).toEqual({ statusId: 's', expectedStatusRevision: 4, expectedFromStatusId: null, datasetGeneration: 'g', recordKeyType: 'text' })
  })

  it('submits an explicit null status from null but rejects an unchanged non-null status', async () => {
    const request = vi.fn().mockResolvedValue(record)
    const props = { workspaceKey: 'w', context: context(), client: client(request), instanceId: 'i', disabled: false, readonly: false, onSaved: vi.fn() }
    const { result } = renderHook(() => useDataTableEditing(props))
    act(() => result.current.open({ kind: 'recordStatus', record }))
    await act(async () => { await result.current.submitRecordStatus(null) })
    expect(request.mock.calls[0][1]?.body).toEqual({ statusId: null, expectedStatusRevision: 4, expectedFromStatusId: null, datasetGeneration: 'g', recordKeyType: 'text' })

    const assigned = { ...record, statusId: 's' }
    act(() => result.current.open({ kind: 'recordStatus', record: assigned }))
    await expect(result.current.submitRecordStatus('s')).rejects.toThrow('记录状态没有修改')
    expect(request).toHaveBeenCalledTimes(1)
  })

  it('uses each catalog directory revision and omits unchanged status edits', async () => {
    const request = vi.fn().mockResolvedValue({ field, tableRevision: 6 })
    const props = { workspaceKey: 'w', context: context(), client: client(request), instanceId: 'i', disabled: false, readonly: false, onSaved: vi.fn() }
    const { result } = renderHook(() => useDataTableEditing(props))
    act(() => result.current.open({ kind: 'fieldCreate' })); await act(async () => { await result.current.submitField({ definition: { key: 'x', name: 'X', type: 'string', required: false, validation: {} }, existingRecordDefault: null }) })
    expect(request.mock.calls[0][1]?.body).toEqual({ definition: { key: 'x', name: 'X', type: 'string', required: false, validation: {} }, expectedTableRevision: 6, sourceColumnPolicy: 'localOnly', existingRecordDefault: null })
    act(() => result.current.open({ kind: 'statusCreate' })); await act(async () => { await result.current.submitStatus({ name: ' New ', color: '#AABBCC', order: 2 }) })
    expect(request.mock.calls[1][1]?.body).toEqual({ name: 'New', color: '#aabbcc', order: 2, expectedTableRevision: 7 })
    act(() => result.current.open({ kind: 'statusEdit', status })); await expect(result.current.submitStatus({})).rejects.toThrow()
    expect(request).toHaveBeenCalledTimes(2)
  })

  it('validates frozen impact reports before field, record, and status deletion writes', async () => {
    const request = vi.fn(async (path: string, init?: ApiRequestInit) => {
      if (path.endsWith('/mutation-impact')) {
        const body = init?.body as { action: string }
        if (body.action === 'updateField') return { impactRevision: 8, target: { type: 'field', fieldRef: field.ref }, expectedRevisions: { tableRevision: 6, fieldRevision: 2 }, changeDigest: 'f', impacts: [], blockers: [], calculatedAt: '2026-01-01T00:00:00Z' }
        if (body.action === 'deleteRecord') return { impactRevision: 9, target: { type: 'record', recordRef: record.ref }, expectedRevisions: { tableRevision: 6, contentRevision: 1, statusRevision: 4, linkRevision: 5 }, changeDigest: 'r', impacts: [], blockers: [], calculatedAt: '2026-01-01T00:00:00Z' }
        return { impactRevision: 10, target: { type: 'status', projectId: 'p', tableId: 't', statusId: 's' }, expectedRevisions: { tableRevision: 7, statusRevision: 3 }, changeDigest: 's', impacts: [], blockers: [], calculatedAt: '2026-01-01T00:00:00Z' }
      }
      const key = (init?.headers as Record<string, string>)['Idempotency-Key']
      if (init?.method === 'DELETE' && path.includes('/records/')) return { operation: { projectId: 'p', idempotencyKey: key, kind: 'deleteRecord', status: 'succeeded', resource: { type: 'record', recordRef: record.ref }, result: { target: { type: 'record', recordRef: record.ref }, deleted: true } } }
      if (init?.method === 'DELETE') return { operation: { projectId: 'p', idempotencyKey: key, kind: 'mutateStatus', status: 'succeeded', resource: { type: 'status', projectId: 'p', tableId: 't', statusId: 's' }, result: { action: 'delete', statusId: 's', deleted: true, tableRevision: 8 } } }
      return { field, tableRevision: 7 }
    })
    const props = { workspaceKey: 'w', context: context(), client: client(request), instanceId: 'i', disabled: false, readonly: false, onSaved: vi.fn() }
    const { result } = renderHook(() => useDataTableEditing(props))
    const definition = { key: 'name', name: 'Renamed', type: 'string' as const, required: false, validation: {} }
    act(() => result.current.open({ kind: 'fieldEdit', field })); await act(async () => { await result.current.previewField(definition) }); await act(async () => { await result.current.submitField({ definition, impactRevision: 8 }) })
    expect(request.mock.calls[1][1]?.body).toEqual({ definition, expectedFieldRevision: 2, expectedTableRevision: 6, impactRevision: 8 })
    act(() => result.current.open({ kind: 'recordDelete', record })); await act(async () => { await result.current.previewDelete() }); await act(async () => { await result.current.confirmDelete() })
    expect(request.mock.calls[3][1]?.body).toEqual({ expectedContentRevision: 1, expectedStatusRevision: 4, expectedLinkRevision: 5, impactRevision: 9, datasetGeneration: 'g', recordKeyType: 'text' })
    act(() => result.current.open({ kind: 'statusDelete', status })); await act(async () => { await result.current.previewDelete() }); await act(async () => { await result.current.confirmDelete() })
    expect(request.mock.calls[5][1]?.body).toEqual({ expectedStatusRevision: 3, expectedTableRevision: 7, impactRevision: 10 })
  })
})

it('blocks leaving synchronously while the active dialog validates or recovers', () => {
  const props = { workspaceKey: 'w', context: context(), client: client(vi.fn()), instanceId: 'i', disabled: false, readonly: false, onSaved: vi.fn() }
  const { result } = renderHook(() => useDataTableEditing(props))
  act(() => result.current.open({ kind: 'recordCreate' }))
  act(() => result.current.onSavingChange(true))
  expect(result.current.canLeave()).toBe(false)
  expect(result.current.close()).toBe(false)
  expect(() => result.current.open({ kind: 'fieldCreate' })).toThrow()
})

it('does not let an old dialog cleanup release the new session busy guard', () => {
  const props = { workspaceKey: 'w', context: context(), client: client(vi.fn()), instanceId: 'i', disabled: false, readonly: false, onSaved: vi.fn() }
  const { result } = renderHook(() => useDataTableEditing(props))
  act(() => result.current.open({ kind: 'recordCreate' }))
  const oldSaving = result.current.onSavingChange
  act(() => result.current.replaceEditor(context(), { kind: 'fieldCreate' }))
  const newSaving = result.current.onSavingChange
  act(() => newSaving(true))
  act(() => oldSaving(false))
  expect(result.current.canLeave()).toBe(false)
})

it('rejects an old submit callback before it can leave a pending command', async () => {
  const request = vi.fn()
  const props = { workspaceKey: 'w', context: context(), client: client(request), instanceId: 'i', disabled: false, readonly: false, onSaved: vi.fn() }
  const { result } = renderHook(() => useDataTableEditing(props))
  act(() => result.current.open({ kind: 'recordCreate' }))
  const oldSubmit = result.current.submitRecord
  act(() => result.current.replaceEditor(context(), { kind: 'fieldCreate' }))
  await expect(oldSubmit([])).rejects.toThrow('编辑会话')
  expect(request).not.toHaveBeenCalled()
  expect(result.current.canLeave()).toBe(true)
  expect(result.current.recoveryPending).toBe(false)
})

it('records an old-scope recovery success without notifying the new scope', async () => {
  const initialRequest = vi.fn().mockRejectedValue(new TypeError('offline'))
  const onSaved = vi.fn()
  const initial = { workspaceKey: 'w', context: context(), client: client(initialRequest), instanceId: 'i', disabled: false, readonly: false, onSaved }
  const { result, rerender } = renderHook(p => useDataTableEditing(p), { initialProps: initial })
  act(() => result.current.open({ kind: 'recordCreate' }))
  await expect(result.current.submitRecord([])).rejects.toThrow()
  const key = (initialRequest.mock.calls[0][1]?.headers as Record<string, string>)['Idempotency-Key']
  const recovered = vi.fn().mockResolvedValue({ projectId: 'p', idempotencyKey: key, kind: 'createRecord', status: 'succeeded', resource: { type: 'record', recordRef: record.ref }, result: record })
  rerender({ ...initial, context: context({ scope: { ...scope, datasetGeneration: 'g2' } }), client: client(recovered), instanceId: 'i2' })
  await act(async () => { await result.current.recover() })
  expect(onSaved).not.toHaveBeenCalled()
  expect(result.current.editor?.kind).toBe('recordCreate')
  expect(result.current.recoveryPending).toBe(false)
  expect(result.current.error).toContain('原数据范围')
  await expect(result.current.submitRecord([])).rejects.toThrow('数据范围')
  expect(recovered).toHaveBeenCalledTimes(1)
})

it('keeps an unknown command frozen without querying through another workspace', async () => {
  const initialRequest = vi.fn().mockRejectedValue(new TypeError('offline'))
  const initial = { workspaceKey: 'w', context: context(), client: client(initialRequest), instanceId: 'i1', disabled: false, readonly: false, onSaved: vi.fn() }
  const { result, rerender } = renderHook(p => useDataTableEditing(p), { initialProps: initial })
  act(() => result.current.open({ kind: 'recordCreate' }))
  await expect(result.current.submitRecord([])).rejects.toThrow()

  const otherWorkspaceRequest = vi.fn().mockRejectedValue(new ApiClientError('absent', 404, 'OPERATION_NOT_FOUND'))
  rerender({ ...initial, workspaceKey: 'w2', context: context({ scope: { ...scope, workspaceKey: 'w2' } }), client: client(otherWorkspaceRequest), instanceId: 'i2' })
  await expect(result.current.recover()).rejects.toThrow('原工作区')
  expect(otherWorkspaceRequest).not.toHaveBeenCalled()
  expect(result.current.recoveryPending).toBe(true)
  expect(result.current.notAccepted).toBe(false)

  const originalWorkspaceLookup = vi.fn().mockResolvedValue({ projectId: 'p', idempotencyKey: (initialRequest.mock.calls[0][1]?.headers as Record<string, string>)['Idempotency-Key'], kind: 'createRecord', status: 'succeeded', resource: { type: 'record', recordRef: record.ref }, result: record })
  rerender({ ...initial, client: client(originalWorkspaceLookup), instanceId: 'i3' })
  await act(async () => { await result.current.recover() })
  expect(originalWorkspaceLookup).toHaveBeenCalledOnce()
  expect(result.current.recoveryPending).toBe(false)
})

it('queries an old-generation pending fact while the editable context is temporarily unavailable', async () => {
  const firstRequest = vi.fn().mockRejectedValue(new TypeError('offline')), onSaved = vi.fn()
  const initial = { workspaceKey: 'w', context: context() as EditingContext | null, client: client(firstRequest), instanceId: 'i1', disabled: false, readonly: false, onSaved }
  const { result, rerender } = renderHook(p => useDataTableEditing(p), { initialProps: initial })
  act(() => result.current.open({ kind: 'recordCreate' }))
  await expect(result.current.submitRecord([])).rejects.toThrow()
  const key = (firstRequest.mock.calls[0][1]?.headers as Record<string, string>)['Idempotency-Key']
  const lookup = vi.fn().mockResolvedValue({ projectId: 'p', idempotencyKey: key, kind: 'createRecord', status: 'succeeded', resource: { type: 'record', recordRef: record.ref }, result: record })
  rerender({ ...initial, context: null, client: client(lookup), instanceId: 'i2' })
  await act(async () => { await result.current.recover() })
  expect(lookup.mock.calls.map(call => call[0])).toEqual([`/api/v1/projects/p/operations/by-idempotency-key/${key}`])
  expect(result.current.recoveryPending).toBe(false)
  expect(onSaved).not.toHaveBeenCalled()
})

it('restores a cold unknown command and only looks up its original key', async () => {
  const firstRequest = vi.fn().mockRejectedValue(new TypeError('offline'))
  const props = { workspaceKey: 'w', context: context(), client: client(firstRequest), instanceId: 'i1', disabled: false, readonly: false, onSaved: vi.fn() }
  const first = renderHook(() => useDataTableEditing(props))
  act(() => first.result.current.open({ kind: 'tableEdit' }))
  await expect(first.result.current.submitTable({ name: 'Renamed', description: table.description })).rejects.toThrow()
  const originalKey = (firstRequest.mock.calls[0][1]?.headers as Record<string, string>)['Idempotency-Key']
  first.unmount()

  const lookup = vi.fn().mockResolvedValue({ projectId: 'p', idempotencyKey: originalKey, kind: 'updateTable', status: 'succeeded', resource: { type: 'table', projectId: 'p', tableId: 't' }, result: { ...table, name: 'Renamed', tableRevision: 2 } })
  const restored = renderHook(() => useDataTableEditing({ ...props, client: client(lookup), instanceId: 'i2' }))
  expect(restored.result.current.editor?.kind).toBe('tableEdit')
  expect(restored.result.current.recoveryPending).toBe(true)
  expect(lookup).not.toHaveBeenCalled()
  await act(async () => { await restored.result.current.recover() })
  expect(lookup.mock.calls.map(call => call[0])).toEqual([`/api/v1/projects/p/operations/by-idempotency-key/${originalKey}`])
  expect(localStorage.length).toBe(0)
})

it('does not send when durable pending storage fails', async () => {
  const request = vi.fn(), props = { workspaceKey: 'w', context: context(), client: client(request), instanceId: 'i', disabled: false, readonly: false, onSaved: vi.fn() }
  const { result } = renderHook(() => useDataTableEditing(props))
  act(() => result.current.open({ kind: 'recordCreate' }))
  const write = vi.spyOn(localStorage, 'setItem').mockImplementation(() => { throw new Error('storage unavailable') })
  await expect(result.current.submitRecord([])).rejects.toThrow('storage unavailable')
  expect(request).not.toHaveBeenCalled()
  expect(result.current.recoveryPending).toBe(false)
  write.mockRestore()
})

it('does not load or delete another table scope pending command', async () => {
  const request = vi.fn().mockRejectedValue(new TypeError('offline'))
  const props = { workspaceKey: 'w', context: context(), client: client(request), instanceId: 'i', disabled: false, readonly: false, onSaved: vi.fn() }
  const first = renderHook(() => useDataTableEditing(props))
  act(() => first.result.current.open({ kind: 'recordCreate' }))
  await expect(first.result.current.submitRecord([])).rejects.toThrow()
  const storedKey = localStorage.key(0)!
  const stored = localStorage.getItem(storedKey)
  first.unmount()

  const other = renderHook(() => useDataTableEditing({ ...props, context: context({ scope: { ...scope, tableId: 'other' } }) }))
  expect(other.result.current.editor).toBeNull()
  expect(other.result.current.recoveryPending).toBe(false)
  expect(localStorage.getItem(storedKey)).toBe(stored)
})

it.each([
  ['unsupported kind', 'future', 'future'],
  ['mismatched editor kind', 'recordCreate', 'tableEdit'],
])('blocks malformed durable recovery with %s without dispatching', (_label, pendingKind, editorKind) => {
  const key = 'autoflow:data-edit:w:p:t', request = vi.fn()
  localStorage.setItem(key, JSON.stringify({
    pending: { kind: pendingKind, key: 'original', session: 'session', scope, body: {} },
    editor: { ...context(), kind: editorKind, session: 'session' },
  }))
  const { result } = renderHook(() => useDataTableEditing({ workspaceKey: 'w', context: context(), client: client(request), instanceId: 'i', disabled: false, readonly: false, onSaved: vi.fn() }))
  expect(result.current.recoveryBlocked).toBe(true)
  expect(result.current.error).toContain('恢复记录不完整')
  expect(() => result.current.open({ kind: 'recordCreate' })).toThrow('禁止写入')
  expect(request).not.toHaveBeenCalled()
  expect(localStorage.getItem(key)).not.toBeNull()
})

it.each([
  ['missing items', { tableRevision: 6 }],
  ['null field', { tableRevision: 6, items: [null] }],
])('blocks a restored schema editor with a corrupt frozen field directory: %s', (_label, fields) => {
  const key = 'autoflow:data-edit:w:p:t', request = vi.fn()
  localStorage.setItem(key, JSON.stringify({
    pending: { kind: 'schemaSave', key: 'original', session: 'session', scope, body: { candidate: schemaCandidate, impactRevision: 12 } },
    editor: { ...context(), fields, kind: 'schemaSave', session: 'session', submittedSchema: schemaCandidate },
  }))
  const { result } = renderHook(() => useDataTableEditing({ workspaceKey: 'w', context: context(), client: client(request), instanceId: 'i', disabled: false, readonly: false, onSaved: vi.fn() }))
  expect(result.current.recoveryBlocked).toBe(true)
  expect(result.current.editor).toBeNull()
  expect(request).not.toHaveBeenCalled()
  expect(localStorage.getItem(key)).not.toBeNull()
})

it.each([
  ['null field', { ...schemaCandidate, fields: [null] }],
  ['missing definition', { ...schemaCandidate, fields: [{ kind: 'existing', fieldId: 'f', expectedFieldRevision: 2 }] }],
  ['invalid field identity', { ...schemaCandidate, fields: [{ kind: 'new', clientId: '', sourceColumnPolicy: 'localOnly', definition: schemaCandidate.fields[0].definition }] }],
])('blocks an unsafe restored schema candidate with %s and retains its evidence', (_label, candidate) => {
  const key = 'autoflow:data-edit:w:p:t', request = vi.fn()
  localStorage.setItem(key, JSON.stringify({
    pending: { kind: 'schemaSave', key: 'original', session: 'session', scope, body: { candidate, impactRevision: 12 } },
    editor: { ...context(), kind: 'schemaSave', session: 'session', submittedSchema: candidate },
  }))
  const { result } = renderHook(() => useDataTableEditing({ workspaceKey: 'w', context: context(), client: client(request), instanceId: 'i', disabled: false, readonly: false, onSaved: vi.fn() }))
  expect(result.current.recoveryBlocked).toBe(true)
  expect(result.current.editor).toBeNull()
  expect(request).not.toHaveBeenCalled()
  expect(localStorage.getItem(key)).not.toBeNull()
})

it('only clears storage when it still contains the completing command key', async () => {
  let resolve!: (value: unknown) => void
  const request = vi.fn(() => new Promise(value => { resolve = value }))
  const { result } = renderHook(() => useDataTableEditing({ workspaceKey: 'w', context: context(), client: client(request), instanceId: 'i', disabled: false, readonly: false, onSaved: vi.fn() }))
  act(() => result.current.open({ kind: 'recordCreate' }))
  let submission!: Promise<unknown>
  act(() => { submission = result.current.submitRecord([]) })
  const key = 'autoflow:data-edit:w:p:t'
  localStorage.setItem(key, JSON.stringify({ pending: { key: 'newer-window-command' } }))
  await act(async () => { resolve(record); await submission })
  expect(JSON.parse(localStorage.getItem(key)!).pending.key).toBe('newer-window-command')
})

it('accepts a record preview whose typed ref has a different property insertion order', async () => {
  const reorderedRef = { recordKey: { value: 'r', type: 'text' as const }, datasetGeneration: 'g', tableId: 't', projectId: 'p' }
  const request = vi.fn().mockResolvedValue({ impactRevision: 9,geltarget: null, target: { type: 'record', recordRef: reorderedRef }, expectedRevisions: { tableRevision: 6, contentRevision: 1, statusRevision: 4, linkRevision: 5 }, changeDigest: 'r', impacts: [], blockers: [], calculatedAt: '2026-01-01T00:00:00Z' })
  const props = { workspaceKey: 'w', context: context(), client: client(request), instanceId: 'i', disabled: false, readonly: false, onSaved: vi.fn() }
  const { result } = renderHook(() => useDataTableEditing(props))
  act(() => result.current.open({ kind: 'recordDelete', record }))
  await act(async () => { await result.current.previewDelete() })
  expect(result.current.impact?.impactRevision).toBe(9)
})

it('rejects non-finite values before serializing durable recovery evidence', async () => {
  const request = vi.fn()
  const { result } = renderHook(() => useDataTableEditing({ workspaceKey: 'w', context: context(), client: client(request), instanceId: 'i', disabled: false, readonly: false, onSaved: vi.fn() }))
  act(() => result.current.open({ kind: 'recordCreate' }))
  const write = vi.spyOn(localStorage, 'setItem')
  await expect(result.current.submitRecord([{ fieldId: 'f', value: Number.NaN }])).rejects.toThrow()
  expect(write).not.toHaveBeenCalled()
  expect(request).not.toHaveBeenCalled()
})

it('restores an unknown UUID record edit after remount and looks up its original operation', async () => {
  const uuidRecord = { ...record, ref: { ...record.ref, recordKey: { type: 'uuid' as const, value: '12345678-1234-4321-8765-123456789abc' } } }
  const offline = vi.fn().mockRejectedValue(new TypeError('offline'))
  const firstProps = { workspaceKey: 'w', context: context(), client: client(offline), instanceId: 'i', disabled: false, readonly: false, onSaved: vi.fn() }
  const first = renderHook(() => useDataTableEditing(firstProps))
  act(() => first.result.current.open({ kind: 'recordEdit', record: uuidRecord }))
  await act(async () => { await expect(first.result.current.submitRecord([{ fieldId: 'f', value: 'new' }])).rejects.toThrow() })
  const key = offline.mock.calls.find(call => call[1]?.method === 'PATCH')![1].headers['Idempotency-Key']
  first.unmount()
  const lookup = vi.fn().mockResolvedValue({ projectId: 'p', idempotencyKey: key, kind: 'updateRecord', status: 'succeeded', resource: { type: 'record', recordRef: uuidRecord.ref }, result: uuidRecord })
  const restored = renderHook(() => useDataTableEditing({ ...firstProps, client: client(lookup), instanceId: 'i2' }))
  expect(restored.result.current.recoveryBlocked).toBe(false)
  expect(restored.result.current.recoveryPending).toBe(true)
  await act(async () => { await restored.result.current.recover() })
  expect(lookup.mock.calls.map(call => call[0])).toEqual([`/api/v1/projects/p/operations/by-idempotency-key/${key}`])
  expect(firstProps.onSaved).toHaveBeenCalledWith('recordEdit', key, uuidRecord)
})
