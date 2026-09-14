// Source: WebRPA@5ccb900e, components/workflow/DebugBar.tsx; see SOURCE.md for license and adaptation boundaries.
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Play, StepForward, Square, Bug, ChevronDown, ChevronUp } from 'lucide-react'
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
  const pausedVariables = useDebugStore((s) => s.pausedVariables)
  const wfId = useWorkflowStore((s) => s.currentExecutionWorkflowId)
  const [showVars, setShowVars] = useState(false)
  type Pending = 'control' | 'stop' | null
  const [busy, setBusy] = useState<Pending>(null)
  const busyRef = useRef<Pending>(null)
  const requestSequence = useRef(0)
  const [error, setError] = useState('')

  useEffect(() => {
    requestSequence.current++
    busyRef.current = null; setBusy(null); setError('')
  }, [wfId, isPaused, pauseRevision])
  useEffect(() => () => { requestSequence.current++ }, [])

  if (!isPaused) return null

  const call = async (fn: ((id: string, context:DebugControlRequest) => Promise<ApiResponse>) | ((id:string)=>Promise<ApiResponse>), kind: Exclude<Pending, null> = 'control') => {
    if (!wfId || (kind==='control' && !pauseContext) || busyRef.current === 'stop' || (kind === 'control' && busyRef.current)) return
    const sequence = ++requestSequence.current
    const isCurrent = () => sequence === requestSequence.current && useDebugStore.getState().isPaused && useDebugStore.getState().pauseRevision === pauseRevision && useWorkflowStore.getState().currentExecutionWorkflowId === wfId
    busyRef.current = kind; setBusy(kind); setError('')
    try {
      const result = kind==='stop'
        ? await (fn as typeof workflowApi.stop)(wfId)
        : await fn(wfId,{...pauseContext!,commandId:crypto.randomUUID()})
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
          {pausedReason === 'step' ? '单步暂停' : '断点暂停'}
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
      </div>

      <div className="flex items-center gap-2 px-4 py-2.5">
        <button
          disabled={!wfId || !pauseContext || !!busy}
          onClick={() => call(workflowApi.debugResume)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500 text-white text-sm font-medium hover:bg-emerald-600 disabled:opacity-50"
        >
          <Play className="w-3.5 h-3.5 fill-current" /> 继续
        </button>
        <button
          disabled={!wfId || !pauseContext || !!busy}
          onClick={() => call(workflowApi.debugStep)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[hsl(var(--brand-600))] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
        >
          <StepForward className="w-3.5 h-3.5" /> 单步
        </button>
        <button
          disabled={!wfId || busy === 'stop'}
          onClick={() => call(workflowApi.stop, 'stop')}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-600 text-white text-sm font-medium hover:bg-slate-700 disabled:opacity-50"
        >
          <Square className="w-3.5 h-3.5 fill-current" /> 停止
        </button>
        <span className="ml-auto text-[11px] text-[hsl(var(--muted-foreground))]">{busy ? '等待执行状态确认' : pausedReason === 'step' ? '单步执行已暂停' : '命中断点已暂停'}</span>
      </div>

      {!pauseContext && <div role="alert" className="px-4 pb-3 text-sm">服务未提供暂停身份，暂不能继续或单步；仍可停止运行。</div>}
      {error && <div role="alert" className="px-4 pb-3 text-sm text-[hsl(var(--danger-600))]">{error}</div>}

      {showVars && (
        <div className="max-h-[220px] border-t border-[hsl(var(--border))] px-3 py-2">
          {varEntries.length === 0 ? (
            <div className="text-[hsl(var(--muted-foreground))] py-2 text-center">暂无变量</div>
          ) : (
            <TableScroll label="暂停变量" className="af-studio-table-scroll max-h-[196px]">
              <Table className="af-studio-table">
              <TableBody>
                {varEntries.map(([k, v]) => (
                  <TableRow key={k}>
                    <TableCell className="font-mono text-[hsl(var(--brand-600))] align-top whitespace-nowrap">{k}</TableCell>
                    <TableCell className="text-[hsl(var(--muted-foreground))] break-all">{fmt(v)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
              </Table>
            </TableScroll>
          )}
        </div>
      )}
    </div>,
    document.body,
  )
}
