// Source: WebRPA@5ccb900e, components/workflow/DebugBar.tsx; see SOURCE.md for license and adaptation boundaries.
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Play, StepForward, Square, Bug, ChevronDown, ChevronUp, Pencil, Check, X, Plus } from 'lucide-react'
import { useDebugStore } from '../hooks/stores/debugStore'
import { useWorkflowStore } from '../editor-store'
import { workflowApi, type ApiResponse } from '../api'
import type {DebugControlRequest} from '../lib/debugControlContract'
import { Table, TableBody, TableCell, TableRow, TableScroll } from '../../../shared/components/ui/table'

/** 调试控制条：命中断点/单步暂停时浮现，提供 继续 / 单步 / 停止 + 当前变量快照 */
export function DebugBar() {
  const pauseContext = useDebugStore((s) => s.pauseContext)
  const pauseRevision = useDebugStore((s) => s.pauseRevision)
  const isPaused = useDebugStore((s) => s.isPaused)
  const pausedLabel = useDebugStore((s) => s.pausedLabel)
  const pausedReason = useDebugStore((s) => s.pausedReason)
  const pausedError = useDebugStore((s) => s.pausedError)
  const pausedVariables = useDebugStore((s) => s.pausedVariables)
  const pausedVariableMeta = useDebugStore((s) => s.pausedVariableMeta)
  const pausedExecutionContext = useDebugStore((s) => s.pausedExecutionContext)
  const wfId = useWorkflowStore((s) => s.currentExecutionWorkflowId)
  const runId = useWorkflowStore((s) => s.currentExecutionRunId)
  const [showVars, setShowVars] = useState(false)
  type Pending = 'control' | 'variables' | 'stop' | null
  const [busy, setBusy] = useState<Pending>(null)
  const busyRef = useRef<Pending>(null)
  const requestSequence = useRef(0)
  const [error, setError] = useState('')
  const [editingVariables, setEditingVariables] = useState(false)
  const [variableDrafts, setVariableDrafts] = useState<Record<string,string>>({})
  const [newVariableName, setNewVariableName] = useState('')
  const [newVariableValue, setNewVariableValue] = useState('null')

  useEffect(() => {
    requestSequence.current++
    busyRef.current = null; setBusy(null); setError(''); setEditingVariables(false); setVariableDrafts({}); setNewVariableName(''); setNewVariableValue('null')
  }, [wfId, runId, isPaused, pauseRevision])
  useEffect(() => () => { requestSequence.current++ }, [])

  if (!isPaused) return null
  const failed = pausedReason === 'failure'
  const contextLabels = [
    ...pausedExecutionContext.scopes.map(scope=>scope.name||scope.id),
    ...pausedExecutionContext.loops.map(loop=>`${loop.nodeId} 第 ${loop.iteration} 轮`),
  ].filter(Boolean)

  const call = async (fn: ((id: string, context:DebugControlRequest) => Promise<ApiResponse>) | typeof workflowApi.stop, kind: Exclude<Pending, null> = 'control') => {
    if (!wfId || !runId || (kind==='control' && (!pauseContext || pauseContext.runId !== runId)) || busyRef.current === 'stop' || (kind === 'control' && busyRef.current)) return
    const sequence = ++requestSequence.current
    const isCurrent = () => sequence === requestSequence.current && useDebugStore.getState().isPaused && useDebugStore.getState().pauseRevision === pauseRevision && useWorkflowStore.getState().currentExecutionWorkflowId === wfId && useWorkflowStore.getState().currentExecutionRunId === runId
    busyRef.current = kind; setBusy(kind); setError('')
    try {
      const result = kind==='stop'
        ? await (fn as typeof workflowApi.stop)(wfId,runId)
        : await (fn as (id: string, context: DebugControlRequest) => Promise<ApiResponse>)(wfId,{...pauseContext!,commandId:crypto.randomUUID()})
      if (!isCurrent()) return
      if (!result.success) {
        if (!result.httpStatus && kind === 'control') {
          setError(`请求结果尚未确认：${result.error || '连接异常'}。请等待状态同步，或停止运行。`)
          return
        }
        setError(result.error || '调试操作被拒绝')
        busyRef.current = null; setBusy(null)
      }
      // HTTP acceptance does not confirm a transition. SSE owns the pause state.
    } catch (cause) {
      if (!isCurrent()) return
      setError(`请求结果尚未确认：${cause instanceof Error ? cause.message : String(cause)}。可停止运行。`)
      if (kind === 'stop') { busyRef.current = null; setBusy(null) }
    }
  }

  const varEntries = Object.entries(pausedVariables || {}).filter(([k]) => k !== 'ERROR')

  const jsonValue = (value:any) => {
    const encoded=JSON.stringify(value)
    return encoded===undefined?'null':encoded
  }

  const beginVariableEdit=()=>{
    setVariableDrafts(Object.fromEntries(varEntries.map(([name,value])=>[name,jsonValue(value)])))
    setEditingVariables(true);setShowVars(true);setError('')
  }

  const applyVariableChanges=async()=>{
    if(!wfId || !runId || !pauseContext || pauseContext.runId!==runId || busyRef.current)return
    const changes:Array<{name:string;value:any}>=[]
    try{
      for(const [name,current] of varEntries){
        if(pausedVariableMeta[name]?.readOnly)continue
        const value=JSON.parse(variableDrafts[name]??jsonValue(current))
        if(JSON.stringify(value)!==JSON.stringify(current))changes.push({name,value})
      }
      const name=newVariableName.trim()
      if(name){
        if(!/^[A-Za-z_][A-Za-z0-9_]*$/.test(name))throw new Error('新变量名只能包含英文字母、数字和下划线，且不能以数字开头')
        if(Object.hasOwn(pausedVariables,name))throw new Error('新变量名已存在')
        changes.push({name,value:JSON.parse(newVariableValue)})
      }
      if(!changes.length)throw new Error('没有需要提交的变量修改')
    }catch(cause){setError(cause instanceof Error?cause.message:String(cause));return}
    const sequence=++requestSequence.current
    const isCurrent=()=>sequence===requestSequence.current && useDebugStore.getState().pauseRevision===pauseRevision && useWorkflowStore.getState().currentExecutionRunId===runId
    busyRef.current='variables';setBusy('variables');setError('')
    let result:ApiResponse
    try{result=await workflowApi.debugVariables(wfId,{...pauseContext,commandId:crypto.randomUUID(),changes})}
    catch(cause){result={success:false,error:cause instanceof Error?cause.message:String(cause)}}
    if(!isCurrent())return
    if(!result.success){
      setError(result.httpStatus?result.error||'变量修改被拒绝':`请求结果尚未确认：${result.error||'连接异常'}。请等待状态同步，或停止运行。`)
      if(result.httpStatus){busyRef.current=null;setBusy(null)}
    }
    // A successful HTTP receipt stays locked until a newer paused event confirms the values.
  }

  const fmt = (v: any) => {
    try {
      if (v === null || v === undefined) return String(v)
      if (typeof v === 'object') { const s = JSON.stringify(v); return s.length > 80 ? s.slice(0, 80) + '…' : s }
      const s = String(v); return s.length > 80 ? s.slice(0, 80) + '…' : s
    } catch { return String(v) }
  }

  return createPortal(
    <div className="fixed top-[72px] left-1/2 -translate-x-1/2 z-[1000] w-[440px] max-w-[92vw] rounded-xl border border-amber-400/60 bg-[hsl(var(--card))] shadow-2xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 bg-amber-50 border-b border-amber-200">
        <Bug className="w-4 h-4 text-amber-600" />
        <span className="text-sm font-semibold text-amber-700">
          {failed ? '失败暂停' : pausedReason === 'step' ? '单步暂停' : pausedReason === 'target' ? '运行至此暂停' : '断点暂停'}
        </span>
        <span className="text-xs text-[hsl(var(--muted-foreground))] truncate max-w-[180px]" title={pausedLabel || ''}>
          @ {pausedLabel}
        </span>
        <button
          className="ml-auto inline-flex items-center gap-1 text-xs text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
          onClick={() => setShowVars((v) => !v)}
        >
          变量 {varEntries.length}
          {showVars ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>
        {showVars && !editingVariables && !failed && (
          <button aria-label="编辑暂停变量" disabled={!pauseContext || !runId || pauseContext.runId!==runId || !!busy} onClick={beginVariableEdit} className="inline-flex items-center gap-1 text-xs text-[hsl(var(--brand-600))] disabled:opacity-50">
            <Pencil className="w-3 h-3" /> 编辑
          </button>
        )}
      </div>

      {contextLabels.length>0&&<div aria-label="调试执行上下文" className="border-b border-amber-200 bg-amber-50/60 px-4 py-1.5 text-[11px] text-amber-800">{contextLabels.join(' / ')}</div>}

      <div className="flex items-center gap-2 px-4 py-2.5">
        {!failed && <button
          disabled={!wfId || !runId || !pauseContext || pauseContext.runId !== runId || !!busy}
          onClick={() => call(workflowApi.debugResume)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500 text-white text-sm font-medium hover:bg-emerald-600 disabled:opacity-50"
        >
          <Play className="w-3.5 h-3.5 fill-current" /> 继续
        </button>}
        {!failed && <button
          disabled={!wfId || !runId || !pauseContext || pauseContext.runId !== runId || !!busy}
          onClick={() => call(workflowApi.debugStep)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[hsl(var(--brand-600))] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
        >
          <StepForward className="w-3.5 h-3.5" /> 单步
        </button>}
        <button
          disabled={!wfId || !runId || busy === 'stop'}
          onClick={() => call(workflowApi.stop, 'stop')}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-600 text-white text-sm font-medium hover:bg-slate-700 disabled:opacity-50"
        >
          <Square className="w-3.5 h-3.5 fill-current" /> {failed ? '结束调试' : '停止'}
        </button>
        <span className="ml-auto text-[11px] text-[hsl(var(--muted-foreground))]">{busy ? '等待执行状态确认' : failed ? '失败现场只读' : pausedReason === 'step' ? '单步执行已暂停' : pausedReason === 'target' ? '已到达调试目标' : '命中断点已暂停'}</span>
      </div>

      {!pauseContext && <div role="alert" className="px-4 pb-3 text-sm">服务未提供暂停身份，暂不能继续或单步；仍可停止运行。</div>}
      {pausedError && <div role="alert" className="px-4 pb-3 text-sm text-[hsl(var(--danger-600))]">{pausedError}</div>}
      {error && <div role="alert" className="px-4 pb-3 text-sm text-[hsl(var(--danger-600))]">{error}</div>}

      {showVars && (
        <div className="max-h-[220px] border-t border-[hsl(var(--border))] px-3 py-2 text-xs">
          {varEntries.length === 0 ? (
            <div className="text-[hsl(var(--muted-foreground))] py-2 text-center">暂无变量</div>
          ) : (
            <TableScroll label="暂停变量" className="max-h-[196px]">
              <Table>
              <TableBody>
                {varEntries.map(([k, v]) => (
                  <TableRow key={k} className="border-b border-[hsl(var(--border))] last:border-0">
                    <TableCell className="py-1 pr-2 font-mono text-[hsl(var(--brand-600))] align-top whitespace-nowrap">{k}{pausedVariableMeta[k]?.readOnly&&<span className="ml-1 rounded bg-slate-100 px-1 text-[10px] text-slate-500">只读</span>}<div className="font-sans text-[10px] text-[hsl(var(--muted-foreground))]">{pausedVariableMeta[k]?.source||''}</div></TableCell>
                    <TableCell className="py-1 text-[hsl(var(--muted-foreground))] break-all">
                      {editingVariables ? <textarea aria-label={`变量 ${k} 的 JSON 值`} disabled={pausedVariableMeta[k]?.readOnly} value={variableDrafts[k]??jsonValue(v)} onChange={event=>setVariableDrafts(current=>({...current,[k]:event.target.value}))} className="w-full min-h-12 rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-2 py-1 font-mono disabled:opacity-60" /> : fmt(v)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
              </Table>
            </TableScroll>
          )}
          {editingVariables && (
            <div className="mt-2 space-y-2 border-t border-[hsl(var(--border))] pt-2">
              <div className="flex items-center gap-2">
                <Plus className="w-3.5 h-3.5" />
                <input aria-label="新调试变量名" value={newVariableName} onChange={event=>setNewVariableName(event.target.value)} placeholder="可选：新变量名" className="h-8 w-36 rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-2 font-mono" />
                <input aria-label="新调试变量 JSON 值" value={newVariableValue} onChange={event=>setNewVariableValue(event.target.value)} className="h-8 min-w-0 flex-1 rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-2 font-mono" />
              </div>
              <div className="text-[11px] text-[hsl(var(--muted-foreground))]">值使用 JSON：字符串需带双引号，支持数字、布尔、列表、对象和 null。</div>
              <div className="flex justify-end gap-2">
                <button disabled={!!busy} onClick={()=>{setEditingVariables(false);setError('')}} className="inline-flex items-center gap-1 rounded border px-2 py-1 disabled:opacity-50"><X className="w-3 h-3"/>取消</button>
                <button disabled={!!busy} onClick={()=>void applyVariableChanges()} className="inline-flex items-center gap-1 rounded bg-[hsl(var(--brand-600))] px-2 py-1 text-white disabled:opacity-50"><Check className="w-3 h-3"/>{busy==='variables'?'等待确认':'应用变量'}</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>,
    document.body,
  )
}
