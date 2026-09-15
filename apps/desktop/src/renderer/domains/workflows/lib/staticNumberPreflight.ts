import type { Edge, Node } from '@xyflow/react'
import type { NodeData } from '../editor-store'
import { parseFiniteNumber } from './finiteNumber'

export type StaticNumberIssue = { nodeId: string; path: string; message: string }
// Frozen workflow_executor.py owns the outer timeout exceptions; excluded node types are omitted.
const internalTimeout = new Set(['loop','foreach','scheduled_task','subflow','view_image','input_prompt','run_workflow_file'])
export function staticNumberIssues(nodes: Node<NodeData>[], edges: Edge[] = [], startNodeId?: string): StaticNumberIssue[] {
  let candidates = nodes
  if (startNodeId && nodes.some(node => node.id === startNodeId)) {
    const outgoing = new Map<string, string[]>()
    for (const edge of edges) outgoing.set(edge.source, [...(outgoing.get(edge.source) || []), edge.target])
    const reachable = new Set<string>()
    const pending = [startNodeId]
    while (pending.length) {
      const id = pending.pop()!
      if (reachable.has(id)) continue
      reachable.add(id)
      pending.push(...(outgoing.get(id) || []))
    }
    candidates = nodes.filter(node => reachable.has(node.id))
  }
  const issues: StaticNumberIssue[] = []
  for (const node of candidates) {
    const data = node.data
    if (data.disabled || ['group','note'].includes(data.moduleType)) continue
    const check = (field: string, label: string, max = Infinity, integer = false, raw: unknown = data[field], min = 0) => {
      // Dynamic templates remain the execution service's responsibility, not a local expression evaluator.
      if (raw === undefined || raw === null || (typeof raw === 'string' && raw.includes('{'))) return
      const value = parseFiniteNumber(raw)
      const message = value === null ? `${label}必须是有限数字` : value < min ? `${label}不能小于${min}`
        : integer && !Number.isInteger(value) ? `${label}必须是整数` : value > max ? `${label}不能大于${max}` : ''
      if (message) issues.push({ nodeId: node.id, path: `data.${field}`, message })
    }
    if (data.moduleType === 'wait_page_load') check('timeout', '页面等待超时', Infinity, false, data.timeout, 1)
    else if (!internalTimeout.has(data.moduleType)) check('timeout','超时时间')
    check('retryCount','重试次数',10,true)
    if ((parseFiniteNumber(data.retryCount) ?? 0) > 0) check('retryDelay','重试间隔')
    if (data.errorPolicy?.mode === 'retry-self' || data.errorPolicy?.mode === 'retry-from') {
      check('errorPolicy.maxRetries', '错误处理重试次数', Infinity, true, data.errorPolicy.maxRetries, 1)
      check('errorPolicy.interval', '错误处理间隔', Infinity, false, data.errorPolicy.interval)
    }
    if (data.moduleType === 'switch_tab' && (!data.switchMode || data.switchMode === 'index')) check('tabIndex', '标签页索引', Infinity, true)
    if (data.moduleType === 'switch_iframe' && (!data.locateBy || data.locateBy === 'index')) check('iframeIndex', 'iframe索引', Infinity, true)
    if (data.moduleType === 'wait_element') check('waitTimeout', '元素等待超时')
    if (data.moduleType === 'wait' && (!data.waitType || data.waitType === 'time')) check('duration','等待时长')
  }
  return issues
}
