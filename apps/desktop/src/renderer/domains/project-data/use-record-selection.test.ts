import { act, renderHook } from '@testing-library/react'
import { expect, it } from 'vitest'
import type { components } from '../../shared/api/generated'
import { useRecordSelection } from './use-record-selection'
type RecordView=components['schemas']['DataRecordView']
const record=(value:string,revision=1,generation='g'):RecordView=>({ref:{projectId:'p',tableId:'t',datasetGeneration:generation,recordKey:{type:'text',value}},values:[],recordSlots:[],statusId:null,currentEnvironmentId:null,contentRevision:1,statusRevision:revision,linkRevision:1,deleted:false,createdAt:'',updatedAt:''})
const scope=(generation='g')=>({workspaceKey:'w',projectId:'p',tableId:'t',datasetGeneration:generation})

it('freezes the complete ref and status revision across page refreshes',()=>{
  const hook=renderHook(()=>useRecordSelection(scope())); const first=record('001',2)
  act(()=>hook.result.current.toggle(first,true)); act(()=>hook.result.current.toggle(record('001',9),true))
  expect(hook.result.current.targets).toEqual([{recordRef:first.ref,expectedStatusRevision:2}])
})
it('retains selection across pages and clears only on full scope change',()=>{
  const hook=renderHook(({generation})=>useRecordSelection(scope(generation)),{initialProps:{generation:'g'}})
  act(()=>hook.result.current.togglePage([record('a'),record('b')],true)); act(()=>hook.result.current.toggle(record('c'),true))
  expect(hook.result.current.count).toBe(3); act(()=>hook.result.current.togglePage([record('a'),record('b')],false)); expect(hook.result.current.targets[0].recordRef.recordKey.value).toBe('c')
  hook.rerender({generation:'g2'}); expect(hook.result.current.count).toBe(0)
})
it('rejects an over-limit page atomically with an explicit message',()=>{
  const hook=renderHook(()=>useRecordSelection(scope())); const records=Array.from({length:1001},(_,i)=>record(String(i)))
  act(()=>hook.result.current.togglePage(records,true)); expect(hook.result.current.count).toBe(0); expect(hook.result.current.error).toContain('1000')
})
it('uses a canonical tuple identity independent of object property insertion order',()=>{
  const hook=renderHook(()=>useRecordSelection(scope())),first=record('same')
  const reordered={...first,ref:{recordKey:first.ref.recordKey,datasetGeneration:'g',tableId:'t',projectId:'p'}} as RecordView
  act(()=>hook.result.current.toggle(first,true)); act(()=>hook.result.current.toggle(reordered,true)); expect(hook.result.current.count).toBe(1)
})
it('revokes old callbacks synchronously on scope change and rejects stale records',()=>{
  const hook=renderHook(({generation})=>useRecordSelection(scope(generation)),{initialProps:{generation:'g'}}),oldToggle=hook.result.current.toggle
  act(()=>oldToggle(record('old'),true)); hook.rerender({generation:'g2'}); expect(hook.result.current.count).toBe(0)
  act(()=>oldToggle(record('late'),true)); expect(hook.result.current.count).toBe(0)
  act(()=>hook.result.current.toggle(record('stale',1,'g'),true)); expect(hook.result.current.error).toContain('当前数据代次'); expect(hook.result.current.count).toBe(0)
})
it('deduplicates a repeated page before enforcing the selection limit',()=>{
  const hook=renderHook(()=>useRecordSelection(scope())),same=record('same')
  act(()=>hook.result.current.togglePage(Array.from({length:1000},()=>same),true)); expect(hook.result.current.count).toBe(1); expect(hook.result.current.error).toBeNull()
})
