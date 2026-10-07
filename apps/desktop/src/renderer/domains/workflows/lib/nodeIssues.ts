import { useMemo } from 'react'
import type { Node } from '@xyflow/react'
import { getNodeConfigData, useWorkflowStore, type NodeData } from '../editor-store'
import { getFieldLabel } from './fieldLabels'
import { getMissingRequired, useRequiredFields } from './requiredFields'
import { staticNumberIssues } from './staticNumberPreflight'

export type NodeIssue = { nodeId: string; field?: string; code: string; message: string; severity: 'error' | 'warning' }
type RequiredMeta = Parameters<typeof getMissingRequired>[2]
export type NodeIssueContext = {
  requiredFields?: RequiredMeta
  conditionalRequired?: Parameters<typeof getMissingRequired>[3]
  fieldLabels?: Record<string, Record<string, string>>
}

const NONE: NodeIssue[] = []
const NO_CONTEXT: NodeIssueContext = {}
const IGNORED_TYPES = ['group', 'note']

export function computeNodeIssues(node: Node<NodeData>, context: NodeIssueContext = NO_CONTEXT): NodeIssue[] {
  const data = getNodeConfigData(node.data)
  if (node.data.disabled || IGNORED_TYPES.includes(data.moduleType)) return []
  const issues: NodeIssue[] = staticNumberIssues([node]).map(issue => ({
    nodeId: node.id,
    field: issue.path.replace(/^data\./, ''),
    code: 'invalid-number',
    message: `${issue.message}，请改成正确的数字，或用 {变量} 引用`,
    severity: 'error',
  }))
  if (context.requiredFields) {
    const labels = context.fieldLabels?.[data.moduleType]
    for (const field of getMissingRequired(String(data.moduleType), data as Record<string, unknown>, context.requiredFields, context.conditionalRequired)) {
      issues.push({ nodeId: node.id, field, code: 'required-missing', message: `「${getFieldLabel(field, labels)}」还没填写，请补全后再运行`, severity: 'error' })
    }
  }
  return issues
}

// Keyed by node.data: dragging a node replaces the node object but keeps data, so its result is reused.
const cache = new WeakMap<object, { nodeId: string; context: NodeIssueContext; issues: NodeIssue[] }>()
function cachedIssues(node: Node<NodeData>, context: NodeIssueContext): NodeIssue[] {
  const hit = cache.get(node.data)
  if (hit && hit.context === context && hit.nodeId === node.id) return hit.issues
  const computed = computeNodeIssues(node, context)
  const issues = computed.length ? computed : NONE
  cache.set(node.data, { nodeId: node.id, context, issues })
  return issues
}

export function computeAllNodeIssues(nodes: Node<NodeData>[], context: NodeIssueContext = NO_CONTEXT): Map<string, NodeIssue[]> {
  const map = new Map<string, NodeIssue[]>()
  for (const node of nodes) {
    const issues = cachedIssues(node, context)
    if (issues.length) map.set(node.id, issues)
  }
  return map
}

function useIssueContext(): NodeIssueContext {
  const { data } = useRequiredFields()
  return useMemo(() => data
    ? { requiredFields: data.requiredFields, conditionalRequired: data.conditionalRequired, fieldLabels: data.fieldLabels }
    : NO_CONTEXT, [data])
}

export function useNodeIssues(nodeId: string): NodeIssue[] {
  const context = useIssueContext()
  return useWorkflowStore(state => {
    const node = state.nodes.find(n => n.id === nodeId)
    return node ? cachedIssues(node, context) : NONE
  })
}

export function useNodeIssueMap(): Map<string, NodeIssue[]> {
  const context = useIssueContext()
  const nodes = useWorkflowStore(state => state.nodes)
  return useMemo(() => computeAllNodeIssues(nodes, context), [nodes, context])
}
