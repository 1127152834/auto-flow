import { useWorkflowStore } from '../editor-store'
import { EXECUTION_SEMANTICS_V2 } from '../types/workflow'

// Remediation M1 R1-06: old documents keep WebRPA error semantics until the user switches.
export function ExecutionSemanticsBanner() {
  const legacy = useWorkflowStore(state => state.executionSemantics !== EXECUTION_SEMANTICS_V2)
  const hasErrorEdges = useWorkflowStore(state => state.edges.some(edge => edge.sourceHandle === 'error'))
  const upgrade = useWorkflowStore(state => state.upgradeExecutionSemantics)
  if (!legacy || !hasErrorEdges) return null
  return (
    <div role="status" className="absolute left-1/2 top-3 z-10 flex -translate-x-1/2 items-center gap-3 rounded-control border border-line bg-surface px-3 py-2 text-sm text-ink shadow-sm">
      <span>这个流程沿用旧的出错规则：错误分支处理后仍算失败。</span>
      <button type="button" className="font-medium text-clay" onClick={upgrade}>改用新规则</button>
    </div>
  )
}
