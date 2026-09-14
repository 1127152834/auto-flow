import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { components } from '../../shared/api/generated'

type Schema=components['schemas']; type RecordView=Schema['DataRecordView']
export type RecordSelectionTarget=Schema['RecordStatusTarget']
export type RecordSelectionScope={workspaceKey:string;projectId:string;tableId:string;datasetGeneration:string}
type State={scopeKey:string;entries:Map<string,RecordSelectionTarget>;error:string|null}
const scopeIdentity=(scope:RecordSelectionScope)=>JSON.stringify([scope.workspaceKey,scope.projectId,scope.tableId,scope.datasetGeneration])
const identity=(record:RecordView)=>JSON.stringify([record.ref.projectId,record.ref.tableId,record.ref.datasetGeneration,record.ref.recordKey.type,record.ref.recordKey.value])
const frozen=(record:RecordView):RecordSelectionTarget=>({recordRef:structuredClone(record.ref),expectedStatusRevision:record.statusRevision})
const belongs=(record:RecordView,scope:RecordSelectionScope)=>record.ref.projectId===scope.projectId&&record.ref.tableId===scope.tableId&&record.ref.datasetGeneration===scope.datasetGeneration

export function useRecordSelection(scope:RecordSelectionScope) {
  const scopeKey=scopeIdentity(scope),currentScope=useRef(scopeKey); currentScope.current=scopeKey
  const [state,setState]=useState<State>(()=>({scopeKey,entries:new Map(),error:null}))
  useEffect(()=>setState(current=>current.scopeKey===scopeKey?current:{scopeKey,entries:new Map(),error:null}),[scopeKey])
  const update=useCallback((change:(current:State)=>State)=>setState(current=>currentScope.current===scopeKey&&current.scopeKey===scopeKey?change(current):current),[scopeKey])
  const toggle=useCallback((record:RecordView,checked:boolean)=>update(current=>{
    if(!belongs(record,scope))return {...current,error:'记录不属于当前数据代次'}
    const key=identity(record),entries=new Map(current.entries)
    if(!checked){entries.delete(key);return {...current,entries,error:null}}
    if(entries.has(key))return current
    if(entries.size>=1000)return {...current,error:'一次最多选择 1000 条记录'}
    entries.set(key,frozen(record));return {...current,entries,error:null}
  }),[scope,update])
  const togglePage=useCallback((records:RecordView[],checked:boolean)=>update(current=>{
    if(records.some(record=>!belongs(record,scope)))return {...current,error:'记录不属于当前数据代次'}
    const unique=new Map(records.map(record=>[identity(record),record])),entries=new Map(current.entries)
    if(!checked){for(const key of unique.keys())entries.delete(key);return {...current,entries,error:null}}
    const additions=[...unique].filter(([key])=>!entries.has(key))
    if(entries.size+additions.length>1000)return {...current,error:'一次最多选择 1000 条记录'}
    for(const [key,record] of additions)entries.set(key,frozen(record));return {...current,entries,error:null}
  }),[scope,update])
  const clear=useCallback(()=>update(current=>({...current,entries:new Map(),error:null})),[update])
  const visible=state.scopeKey===scopeKey?state:{scopeKey,entries:new Map<string,RecordSelectionTarget>(),error:null}
  const targets=useMemo(()=>[...visible.entries.values()],[visible.entries])
  const isSelected=useCallback((record:RecordView)=>visible.entries.has(identity(record)),[visible.entries])
  return {targets,count:targets.length,error:visible.error,isSelected,toggle,togglePage,clear}
}
export type RecordSelection=ReturnType<typeof useRecordSelection>
