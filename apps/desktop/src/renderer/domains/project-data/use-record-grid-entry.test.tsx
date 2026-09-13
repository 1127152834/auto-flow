import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { useRecordGridEntry } from './use-record-grid-entry'
import { scalarDraft } from './scalar-draft'
import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'

afterEach(cleanup)
const scope = { workspaceId: 'w', projectId: crypto.randomUUID(), tableId: crypto.randomUUID(), datasetGeneration: crypto.randomUUID() }
const field = { ref: { ...scope, fieldId: crypto.randomUUID() }, key: 'title', name: '标题', type: 'string' as const, required: true, validation: {}, writable: true, formula: false, fieldRevision: 1 }
function storage() { const map = new Map<string, string>(); return { getItem: (k:string) => map.get(k) ?? null, setItem: (k:string,v:string) => { map.set(k,v) } } }
function resultFor(key:string, body:{rows:{clientRowId:string}[]}) {
 const result = { records: body.rows.map(row => ({ clientRowId: row.clientRowId, record: { ref: { projectId:scope.projectId, tableId:scope.tableId,datasetGeneration:scope.datasetGeneration,recordKey:{type:'uuid',value:crypto.randomUUID()} }, values:[], statusId:null, currentEnvironmentId:null, recordSlots:[], contentRevision:1,statusRevision:1,linkRevision:1,deleted:false,createdAt:'2026-09-14T00:00:00Z',updatedAt:'2026-09-14T00:00:00Z' } })) }
 return { projectId:scope.projectId,idempotencyKey:key,kind:'createRecords',status:'succeeded', resource:{type:'table',projectId:scope.projectId,tableId:scope.tableId},result }
}
function options(request: StreamingApiClient['request']) { return { scope, instanceKey:'i1', fields:[field],tableRevision:2,writable:true,client:{request,health:vi.fn(),stream:vi.fn()},storage:storage(),onSaved:vi.fn() } }
async function enter(hook: ReturnType<typeof renderHook<ReturnType<typeof useRecordGridEntry>, ReturnType<typeof options>>>){
 act(() => hook.result.current.addRow())
 act(() => hook.result.current.changeCell(hook.result.current.rows[0].clientRowId,field.ref.fieldId,scalarDraft('温室')))
}
it('persists pending before POST, freezes duplicate save, and clears only after validated success',async()=>{
 let release: (value:unknown)=>void = ()=>{}
 const request = vi.fn().mockImplementation((_url,init)=>new Promise(resolve=>{ release=()=>resolve({operation:resultFor(init.headers['Idempotency-Key'],init.body)}) }))
 const opts=options(request), hook=renderHook(()=>useRecordGridEntry(opts))
 await enter(hook)
 let first:Promise<void>=Promise.resolve()
 act(()=>{first=hook.result.current.save(); void hook.result.current.save()})
 expect(request).toHaveBeenCalledTimes(1)
 expect(hook.result.current.state).toBe('submitting')
 await act(async()=>{release({});await first})
 expect(hook.result.current.rows).toHaveLength(0)
 expect(opts.onSaved).toHaveBeenCalledOnce()
})
it('keeps the original pending payload after lost response and recovers after remount',async()=>{
 let accepted:unknown
 const request=vi.fn().mockImplementation((_url,init)=>{ if(init?.method==='POST') accepted=resultFor(init.headers['Idempotency-Key'],init.body); return Promise.reject(new TypeError('offline')) })
 const opts=options(request), hook=renderHook(()=>useRecordGridEntry(opts))
 await enter(hook); await act(async()=>hook.result.current.save())
 expect(hook.result.current.state).toBe('uncertain')
 hook.unmount()
 request.mockResolvedValue(accepted)
 const recovered=renderHook(()=>useRecordGridEntry({...opts,instanceKey:'i2'}))
 await act(async()=>recovered.result.current.reconcile())
 expect(recovered.result.current.rows).toHaveLength(0)
 expect(request.mock.calls.filter(([,init])=>init?.method==='POST')).toHaveLength(1)
})
it('blocks submission when persistent storage fails',async()=>{
 const request=vi.fn(), opts=options(request), hook=renderHook(()=>useRecordGridEntry(opts))
 await enter(hook); opts.storage.setItem=()=>{throw new Error('quota')}
 await act(async()=>hook.result.current.save())
 expect(request).not.toHaveBeenCalled();expect(hook.result.current.message).toContain('quota')
})
it('ignores a response from the previous service instance without clearing stored pending',async()=>{
 let release:()=>void=()=>{}
 const request=vi.fn().mockImplementation((_url,init)=>new Promise(resolve=>{release=()=>resolve({operation:resultFor(init.headers['Idempotency-Key'],init.body)})}))
 const opts=options(request), hook=renderHook(p=>useRecordGridEntry(p),{initialProps:opts})
 await enter(hook); let task:Promise<void>=Promise.resolve();act(()=>{task=hook.result.current.save()})
 hook.rerender({...opts,instanceKey:'i2'})
 await act(async()=>{release();await task})
 await waitFor(()=>expect(hook.result.current.rows).toHaveLength(1))
 expect(opts.onSaved).not.toHaveBeenCalled()
})
it('preserves pending on payload mismatch rather than minting a new operation identity',async()=>{
 const request=vi.fn().mockRejectedValue(new ApiClientError('mismatch',409,'OPERATION_PAYLOAD_MISMATCH',{})),opts=options(request)
 const hook=renderHook(()=>useRecordGridEntry(opts));await enter(hook)
 await act(async()=>hook.result.current.save())
 expect(hook.result.current.pending).toBe(true)
 expect(hook.result.current.state).toBe('uncertain')
 expect(hook.result.current.editable).toBe(false)
})
it('keeps drafts after a schema revision changes and only resumes after explicit confirmation',async()=>{
 const opts=options(vi.fn()),hook=renderHook(p=>useRecordGridEntry(p),{initialProps:opts});await enter(hook)
 hook.rerender({...opts,tableRevision:3})
 expect(hook.result.current.state).toBe('stale');expect(hook.result.current.editable).toBe(false)
 act(()=>hook.result.current.adoptSchema())
 expect(hook.result.current.editable).toBe(true);expect(hook.result.current.rows[0].cells[field.ref.fieldId].text).toBe('温室')
})
it('can query an old-generation pending operation after remount without adding into the new generation',async()=>{
 let accepted:unknown
 const request=vi.fn().mockImplementation((_url,init)=>{if(init?.method==='POST')accepted=resultFor(init.headers['Idempotency-Key'],init.body);return Promise.reject(new TypeError('offline'))})
 const opts=options(request),hook=renderHook(()=>useRecordGridEntry(opts));await enter(hook);await act(async()=>hook.result.current.save());hook.unmount()
 request.mockResolvedValue(accepted)
 const newScope={...scope,datasetGeneration:crypto.randomUUID()}
 const recovered=renderHook(()=>useRecordGridEntry({...opts,scope:newScope}))
 expect(recovered.result.current.pending).toBe(true)
 await act(async()=>recovered.result.current.reconcile())
 expect(recovered.result.current.rows).toHaveLength(0)
 expect(recovered.result.current.editable).toBe(true)
 expect(opts.onSaved).not.toHaveBeenCalled()
 expect(request.mock.calls.filter(([,init])=>init?.method==='POST')).toHaveLength(1)
})
it('blocks an old-generation draft until explicitly discarded and leaves other-workspace drafts isolated',async()=>{
 const opts=options(vi.fn()),hook=renderHook(()=>useRecordGridEntry(opts));await enter(hook);hook.unmount()
 const other=renderHook(()=>useRecordGridEntry({...opts,scope:{...scope,workspaceId:'other'}}));expect(other.result.current.rows).toHaveLength(0);other.unmount()
 const newScope={...scope,datasetGeneration:crypto.randomUUID()}
 const recovered=renderHook(()=>useRecordGridEntry({...opts,scope:newScope}))
 expect(recovered.result.current.rows).toHaveLength(1);expect(recovered.result.current.editable).toBe(false)
 act(()=>recovered.result.current.adoptSchema());expect(recovered.result.current.editable).toBe(false)
 act(()=>recovered.result.current.discard());expect(recovered.result.current.editable).toBe(true)
})
