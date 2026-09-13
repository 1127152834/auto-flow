import type { WorkflowContent, WorkflowEdge, WorkflowNode } from './types'

export const controlTypes = new Set(['condition', 'condition_end', 'loop', 'loop_end', 'break_loop', 'continue_loop', 'set_variable'])
export const isOpener = (node: WorkflowNode) => node.type === 'condition' || node.type === 'loop'
export const ports = (node: WorkflowNode): WorkflowEdge['sourceHandle'][] => node.type === 'condition' ? ['true', 'false'] : node.type === 'loop' ? ['body', 'done'] : ['loop_end', 'break_loop', 'continue_loop'].includes(node.type) ? [] : ['out']

/** Membership uses graph reachability, stopping at each paired boundary. */
export function blockNodes(content: WorkflowContent, openerId: string): string[] {
  const nodes = new Map(content.document.nodes.map(node => [node.id, node]))
  const opener = nodes.get(openerId)
  if (!opener || !isOpener(opener)) return [openerId]
  const found = new Set<string>([openerId])
  const end = String(opener.config.endNodeId ?? '')
  if (nodes.has(end)) found.add(end)
  const pending = content.document.edges.filter(edge => edge.source === openerId && (opener.type === 'condition' || edge.sourceHandle === 'body')).map(edge => edge.target)
  while (pending.length) {
    const id = pending.pop()!
    if (id === end || found.has(id)) continue
    found.add(id)
    const node = nodes.get(id)
    if (node && isOpener(node) && typeof node.config.endNodeId === 'string') found.add(node.config.endNodeId)
    for (const edge of content.document.edges) if (edge.source === id || node && isOpener(node) && edge.source === node.config.endNodeId) pending.push(edge.target)
  }
  return [...found]
}

export function expandBlocks(content: WorkflowContent, ids: string[]): string[] {
  const expanded = new Set(ids.flatMap(id => blockNodes(content, id)))
  for (const node of content.document.nodes) if (node.type.endsWith('_end') && !expanded.has(String(node.config.ownerNodeId))) expanded.delete(node.id)
  return [...expanded]
}

export function localVariables(content: WorkflowContent, nodeId: string): string[] {
  return content.document.nodes.filter(node => node.type === 'loop' && node.id !== nodeId && blockNodes(content, node.id).includes(nodeId)).flatMap(node => [String(node.config.indexVariable), ...(node.config.mode === 'foreach' ? [String(node.config.itemVariable)] : [])])
}

export function mapReferences(value: unknown, oldName: string, newName: string, replaceText: (text: string) => string, literals = new Set<string>(), path = 'config'): unknown {
  if (literals.has(path)) return value
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const source = value as Record<string, unknown>
    if (source.kind === 'literal') return value
    if (source.kind === 'variable') return { ...source, name: source.name === oldName ? newName : source.name }
    return Object.fromEntries(Object.entries(source).map(([key, item]) => [key, mapReferences(item, oldName, newName, replaceText, literals, `${path}.${key}`)]))
  }
  if (Array.isArray(value)) return value.map((item, index) => mapReferences(item, oldName, newName, replaceText, literals, `${path}.${index}`))
  return typeof value === 'string' ? replaceText(value) : value
}
