import type { NodeDefinition, Point, WorkflowContent, WorkflowNode } from './types'

export function createWorkflow(): WorkflowContent {
  return {
    document: { id: crypto.randomUUID(), name: '未命名流程', schemaVersion: 1, nodes: [], edges: [], variables: [] },
    layout: { nodes: {}, viewport: { x: 0, y: 0, zoom: 1 } },
  }
}

function ordered(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(ordered)
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, ordered(item)]))
  return value
}

/** Camera movement is saved explicitly, but never prompts the user to save. */
export function signature(content: WorkflowContent): string {
  return JSON.stringify(ordered({ document: content.document, positions: content.layout.nodes }))
}

export function addNode(content: WorkflowContent, definition: NodeDefinition, point: Point): WorkflowContent {
  const id = crypto.randomUUID()
  const node: WorkflowNode = { id, type: definition.type, label: definition.title, config: structuredClone(definition.defaultConfig) }
  return { document: { ...content.document, nodes: [...content.document.nodes, node] }, layout: { ...content.layout, nodes: { ...content.layout.nodes, [id]: point } } }
}

export function patchNode(content: WorkflowContent, id: string, patch: Partial<Pick<WorkflowNode, 'label'>> & { config?: Record<string, unknown> }): WorkflowContent {
  return { ...content, document: { ...content.document, nodes: content.document.nodes.map(node => node.id === id ? { ...node, ...patch, config: { ...node.config, ...patch.config } } as WorkflowNode : node) } }
}

export function connectNodes(content: WorkflowContent, source: string, target: string): { content: WorkflowContent; error?: string } {
  const ids = new Set(content.document.nodes.map(node => node.id))
  const edges = content.document.edges
  if (!ids.has(source) || !ids.has(target)) return { content, error: '连线引用的节点不存在' }
  if (source === target) return { content, error: '不能连接节点自身' }
  if (edges.some(edge => edge.source === source && edge.target === target)) return { content, error: '这条连线已经存在' }
  if (edges.some(edge => edge.source === source || edge.target === target)) return { content, error: '顺序节点每个端口只能连接一个节点' }
  const visited = new Set<string>()
  const pending = [target]
  while (pending.length) {
    const id = pending.pop()!
    if (id === source) return { content, error: '此连接会形成回环' }
    if (visited.has(id)) continue
    visited.add(id)
    edges.filter(edge => edge.source === id).forEach(edge => pending.push(edge.target))
  }
  return { content: { ...content, document: { ...content.document, edges: [...edges, { id: crypto.randomUUID(), source, target, sourceHandle: 'out', targetHandle: 'in' }] } } }
}

export function deleteSelection(content: WorkflowContent, nodeIds: string[], edgeIds: string[]): WorkflowContent {
  const nodes = new Set(nodeIds)
  const edges = new Set(edgeIds)
  return {
    document: { ...content.document, nodes: content.document.nodes.filter(node => !nodes.has(node.id)), edges: content.document.edges.filter(edge => !edges.has(edge.id) && !nodes.has(edge.source) && !nodes.has(edge.target)) },
    layout: { ...content.layout, nodes: Object.fromEntries(Object.entries(content.layout.nodes).filter(([id]) => !nodes.has(id))) },
  }
}

export function pasteNodes(content: WorkflowContent, clipboard: WorkflowContent, selectedIds: string[], anchor: Point): { content: WorkflowContent; ids: string[] } {
  const selected = clipboard.document.nodes.filter(node => selectedIds.includes(node.id))
  if (!selected.length) return { content, ids: [] }
  const mapping = new Map(selected.map(node => [node.id, crypto.randomUUID()]))
  const positions = selected.map(node => clipboard.layout.nodes[node.id])
  const origin = { x: Math.min(...positions.map(p => p.x)), y: Math.min(...positions.map(p => p.y)) }
  const nodes = selected.map(node => ({ ...structuredClone(node), id: mapping.get(node.id)! }))
  const edges = clipboard.document.edges.filter(edge => mapping.has(edge.source) && mapping.has(edge.target)).map(edge => ({ ...edge, id: crypto.randomUUID(), source: mapping.get(edge.source)!, target: mapping.get(edge.target)! }))
  const layout = Object.fromEntries(selected.map(node => [mapping.get(node.id)!, { x: anchor.x + clipboard.layout.nodes[node.id].x - origin.x, y: anchor.y + clipboard.layout.nodes[node.id].y - origin.y }]))
  return { ids: nodes.map(node => node.id), content: { document: { ...content.document, nodes: [...content.document.nodes, ...nodes], edges: [...content.document.edges, ...edges] }, layout: { ...content.layout, nodes: { ...content.layout.nodes, ...layout } } } }
}

const referencePattern = /\$\{([\p{L}_][\p{L}\p{N}_]*)\}|(?<![${])\{([\p{L}_][\p{L}\p{N}_]*)\}(?!\})/gu
function mapText(value: unknown, transform: (text: string) => string): unknown {
  if (typeof value === 'string') return transform(value)
  if (Array.isArray(value)) return value.map(item => mapText(item, transform))
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, mapText(item, transform)]))
  return value
}

export function referencedVariables(value: unknown): string[] {
  const found: string[] = []
  mapText(value, text => { for (const match of text.matchAll(referencePattern)) found.push(match[1] ?? match[2]); return text })
  return found
}

export function renameVariable(content: WorkflowContent, oldName: string, newName: string): WorkflowContent {
  const replace = (text: string) => text.replace(referencePattern, (match, standard: string | undefined, short: string | undefined) => (standard ?? short) === oldName ? `${standard ? '$' : ''}{${newName}}` : match)
  return { ...content, document: { ...content.document,
    nodes: content.document.nodes.map(node => {
      const config = mapText(node.config, replace) as WorkflowNode['config']
      if ((node.type === 'get_element_info' || node.type === 'screenshot') && config.variableName === oldName) config.variableName = newName
      return { ...node, config }
    }),
    variables: content.document.variables.map(variable => ({ ...variable, name: variable.name === oldName ? newName : variable.name, value: mapText(variable.value, replace) as typeof variable.value })),
  } }
}
