import { expect, it } from 'vitest'
import { readGridSession, writeGridSession, type GridSession, type GridScope } from './record-grid-storage'
import { newDraftRow } from './record-grid-draft'
const scope: GridScope = { workspaceId: 'w', projectId: crypto.randomUUID(), tableId: crypto.randomUUID(), datasetGeneration: crypto.randomUUID() }
const field = { ref: { projectId: scope.projectId, tableId: scope.tableId, datasetGeneration: scope.datasetGeneration, fieldId: crypto.randomUUID() }, key: 'title', name: '标题', type: 'string' as const, required: false, validation: {}, writable: true, formula: false, fieldRevision: 1 }
function store() { const map = new Map<string,string>(); return { getItem: (k:string) => map.get(k) ?? null, setItem: (k:string,v:string) => { map.set(k,v) } } }
function draft(): GridSession { return { schemaVersion: 1, scope, tableRevision: 2, rows: [newDraftRow([field])], pending: null, receipt: null } }
it('restores stable workspace draft and isolates generation and workspace', () => {
 const storage = store(), value = draft()
 writeGridSession(storage, value)
 expect(readGridSession(storage, scope)).toEqual(value)
 expect(readGridSession(storage, { ...scope, workspaceId: 'other' })).toBeNull()
 expect(() => readGridSession(storage, { ...scope, datasetGeneration: crypto.randomUUID() })).toThrow('数据已更新')
})
it('rejects corrupted data, unsupported versions and forged command scope', () => {
 const storage = store(), value = draft()
 writeGridSession(storage, value)
 const originalRead = storage.getItem
 storage.getItem = () => '{ broken'
 expect(() => readGridSession(storage, scope)).toThrow('草稿')
 storage.getItem = () => JSON.stringify({ ...value, schemaVersion: 9 })
 expect(() => readGridSession(storage, scope)).toThrow('草稿')
 storage.getItem = originalRead
 expect(() => writeGridSession(storage, { ...value, pending: { key: crypto.randomUUID(), payload: { datasetGeneration: crypto.randomUUID(), expectedTableRevision: 2, rows: [{ clientRowId: value.rows[0].clientRowId, values: [] }] } } })).toThrow('草稿')
})
it('does not hide persistent-storage failures', () => {
 expect(() => writeGridSession({ setItem: () => { throw new Error('quota') } }, draft())).toThrow('quota')
})
