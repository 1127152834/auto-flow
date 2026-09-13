// Source: WebRPA@5ccb900e, components/workflow/DebugBar.tsx; see SOURCE.md for license and adaptation boundaries.
import { useState } from 'react'
import { createPortal } from 'react-dom'
import { Play, StepForward, Square, Bug, ChevronDown, ChevronUp } from 'lucide-react'
import { useDebugStore } from '../hooks/stores/debugStore'
import { useWorkflowStore } from '../editor-store'
import { workflowApi } from '../api'

/** 调试控制条：命中断点/单步暂停时浮现，提供 继续 / 单步 / 停止 + 当前变量快照 */
export function DebugBar() {
  const isPaused = useDebugStore((s) => s.isPaused)
  const pausedLabel = useDebugStore((s) => s.pausedLabel)
  const pausedReason = useDebugStore((s) => s.pausedReason)
  const pausedVariables = useDebugStore((s) => s.pausedVariables)
  const wfId = useWorkflowStore((s) => s.currentExecutionWorkflowId)
  const [showVars, setShowVars] = useState(false)
  const [busy, setBusy] = useState(false)

  if (!isPaused) return null

  const call = async (fn: (id: string) => Promise<any>) => {
    if (!wfId || busy) return
    setBusy(true)
    try { await fn(wfId) } catch {} finally { setBusy(false) }
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
          disabled={busy}
          onClick={() => call(workflowApi.debugResume)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500 text-white text-sm font-medium hover:bg-emerald-600 disabled:opacity-50"
        >
          <Play className="w-3.5 h-3.5 fill-current" /> 继续
        </button>
        <button
          disabled={busy}
          onClick={() => call(workflowApi.debugStep)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[hsl(var(--brand-600))] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
        >
          <StepForward className="w-3.5 h-3.5" /> 单步
        </button>
        <button
          disabled={busy}
          onClick={() => call(workflowApi.stop)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-600 text-white text-sm font-medium hover:bg-slate-700 disabled:opacity-50"
        >
          <Square className="w-3.5 h-3.5 fill-current" /> 停止
        </button>
        <span className="ml-auto text-[11px] text-[hsl(var(--muted-foreground))]">命中断点已暂停</span>
      </div>

      {showVars && (
        <div className="max-h-[220px] overflow-y-auto border-t border-[hsl(var(--border))] px-3 py-2 text-xs">
          {varEntries.length === 0 ? (
            <div className="text-[hsl(var(--muted-foreground))] py-2 text-center">暂无变量</div>
          ) : (
            <table className="w-full">
              <tbody>
                {varEntries.map(([k, v]) => (
                  <tr key={k} className="border-b border-[hsl(var(--border))] last:border-0">
                    <td className="py-1 pr-2 font-mono text-[hsl(var(--brand-600))] align-top whitespace-nowrap">{k}</td>
                    <td className="py-1 text-[hsl(var(--muted-foreground))] break-all">{fmt(v)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>,
    document.body,
  )
}
