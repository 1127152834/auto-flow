import { blockNodes, expandBlocks, localVariables, mapReferences, ports } from './control-model'
import type { NodeDefinition, Point, WorkflowEdge, WorkflowContent, WorkflowDocument, WorkflowNode } from './types'

export function createWorkflow(): WorkflowContent {
  return {
    document: { id: crypto.randomUUID(), name: '未命名流程', schemaVersion: 3, nodes: [], edges: [], variables: [] },
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
  return JSON.stringify(ordered({ document: { ...content.document, schemaVersion: 3, nodes: content.document.nodes.map(n => ({ ...n, literalPaths: n.literalPaths ?? [] })) }, positions: content.layout.nodes }))
}

/** Run markers compare the normalized document only, never saved/dirty state or layout. */
export function documentSignature(document: WorkflowDocument, catalog: NodeDefinition[]): string {
  return JSON.stringify(ordered({ ...document, schemaVersion: 3, nodes: document.nodes.map(node => ({ ...node, literalPaths: node.literalPaths ?? [], config: { ...catalog.find(item => item.type === node.type)?.defaultConfig, ...node.config } })) }))
}

export function addNode(content: WorkflowContent, definition: NodeDefinition, point: Point): WorkflowContent {
  const id = crypto.randomUUID()
  const node: WorkflowNode = { id, type: definition.type, label: definition.title, config: structuredClone(definition.defaultConfig) }
  if (definition.type === 'condition' || definition.type === 'loop') {
    const end = crypto.randomUUID()
    node.config.endNodeId = end
    const closing: WorkflowNode = { id: end, type: definition.type === 'condition' ? 'condition_end' : 'loop_end', label: definition.type === 'condition' ? '条件结束' : '循环结束', config: { ownerNodeId: id, timeoutSeconds: 60 } }
    const handles: WorkflowEdge['sourceHandle'][] = definition.type === 'condition' ? ['true', 'false'] : ['body']
    const edges: WorkflowEdge[] = handles.map(sourceHandle => ({ id: crypto.randomUUID(), source: id, target: end, sourceHandle, targetHandle: 'in' }))
    return { document: { ...content.document, schemaVersion: 3, nodes: [...content.document.nodes, node, closing], edges: [...content.document.edges, ...edges] }, layout: { ...content.layout, nodes: { ...content.layout.nodes, [id]: point, [end]: { x: point.x + 330, y: point.y + 180 } } } }
  }
  return { document: { ...content.document, schemaVersion: 3, nodes: [...content.document.nodes, node] }, layout: { ...content.layout, nodes: { ...content.layout.nodes, [id]: point } } }
}

export function patchNode(content: WorkflowContent, id: string, patch: Partial<Pick<WorkflowNode, 'label' | 'literalPaths'>> & { config?: Record<string, unknown> }): WorkflowContent {
  return { ...content, document: { ...content.document, nodes: content.document.nodes.map(node => node.id === id ? { ...node, ...patch, config: { ...node.config, ...patch.config } } as WorkflowNode : node) } }
}

export function connectNodes(content: WorkflowContent, source: string, target: string, sourceHandle: WorkflowEdge["sourceHandle"] = "out"): { content: WorkflowContent; error?: string } {
  const ids = new Set(content.document.nodes.map(node => node.id))
  const edges = content.document.edges
  if (!ids.has(source) || !ids.has(target)) return { content, error: '连线引用的节点不存在' }
  if (source === target) return { content, error: '不能连接节点自身' }
  if (edges.some(edge => edge.source === source && edge.target === target && edge.sourceHandle === sourceHandle)) return { content, error: '这条连线已经存在' }
  const sourceNode = content.document.nodes.find(node => node.id === source)!
  const targetNode = content.document.nodes.find(node => node.id === target)!
  if (!ports(sourceNode).includes(sourceHandle)) return { content, error: '节点没有此输出端口' }
  if (edges.some(edge => edge.source === source && edge.sourceHandle === sourceHandle || edge.target === target && targetNode.type !== 'condition_end')) return { content, error: '每个输出端口只能连接一个节点；仅条件结束节点允许汇合' }
  const visited = new Set<string>()
  const pending = [target]
  while (pending.length) {
    const id = pending.pop()!
    if (id === source) return { content, error: '此连接会形成回环' }
    if (visited.has(id)) continue
    visited.add(id)
    edges.filter(edge => edge.source === id).forEach(edge => pending.push(edge.target))
  }
  return { content: { ...content, document: { ...content.document, edges: [...edges, { id: crypto.randomUUID(), source, target, sourceHandle, targetHandle: 'in' }] } } }
}

export function deleteSelection(content: WorkflowContent, nodeIds: string[], edgeIds: string[]): WorkflowContent {
  const nodes = new Set(expandBlocks(content, nodeIds))
  const edges = new Set(edgeIds)
  return {
    document: { ...content.document, nodes: content.document.nodes.filter(node => !nodes.has(node.id)), edges: content.document.edges.filter(edge => !edges.has(edge.id) && !nodes.has(edge.source) && !nodes.has(edge.target)) },
    layout: { ...content.layout, ...(content.layout.breakpoints ? { breakpoints: content.layout.breakpoints.filter(id => !nodes.has(id)) } : {}), nodes: Object.fromEntries(Object.entries(content.layout.nodes).filter(([id]) => !nodes.has(id))) },
  }
}

export function pasteNodes(content: WorkflowContent, clipboard: WorkflowContent, selectedIds: string[], anchor: Point): { content: WorkflowContent; ids: string[] } {
  const expanded = expandBlocks(clipboard, selectedIds)
  const selected = clipboard.document.nodes.filter(node => expanded.includes(node.id))
  if (!selected.length) return { content, ids: [] }
  const mapping = new Map(selected.map(node => [node.id, crypto.randomUUID()]))
  const positions = selected.map(node => clipboard.layout.nodes[node.id])
  const origin = { x: Math.min(...positions.map(p => p.x)), y: Math.min(...positions.map(p => p.y)) }
  const nodes = selected.map(node => {
    const copy = { ...structuredClone(node), id: mapping.get(node.id)! }
    for (const field of ['ownerNodeId', 'endNodeId']) if (typeof copy.config[field] === 'string') copy.config[field] = mapping.get(copy.config[field]) ?? copy.config[field]
    return copy
  })
  const edges = clipboard.document.edges.filter(edge => mapping.has(edge.source) && mapping.has(edge.target)).map(edge => ({ ...edge, id: crypto.randomUUID(), source: mapping.get(edge.source)!, target: mapping.get(edge.target)! }))
  const layout = Object.fromEntries(selected.map(node => [mapping.get(node.id)!, { x: anchor.x + clipboard.layout.nodes[node.id].x - origin.x, y: anchor.y + clipboard.layout.nodes[node.id].y - origin.y }]))
  return { ids: nodes.map(node => node.id), content: { document: { ...content.document, nodes: [...content.document.nodes, ...nodes], edges: [...content.document.edges, ...edges] }, layout: { ...content.layout, breakpoints: [...(content.layout.breakpoints ?? []), ...(clipboard.layout.breakpoints ?? []).filter(id => mapping.has(id)).map(id => mapping.get(id)!)], nodes: { ...content.layout.nodes, ...layout } } } }
}

const referencePattern = /\$\{([\p{L}_][\p{L}\p{N}_]*)\}|(?<![${])\{([\p{L}_][\p{L}\p{N}_]*)\}(?!\})/gu
function mapText(value: unknown, transform: (text: string) => string): unknown {
  if (typeof value === 'string') return transform(value)
  if (Array.isArray(value)) return value.map(item => mapText(item, transform))
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, mapText(item, transform)]))
  return value
}

export function referencedVariables(value: unknown, typedSources = false): string[] {
  const found: string[] = []
  const scan = (current: unknown): void => {
    if (current && typeof current === 'object' && !Array.isArray(current)) {
      const source = current as Record<string, unknown>
      if (typedSources && source.kind === 'literal') return
      if (typedSources && source.kind === 'variable') { if (typeof source.name === 'string') found.push(source.name); return }
      Object.values(source).forEach(scan)
    } else if (Array.isArray(current)) current.forEach(scan)
    else if (typeof current === 'string') for (const match of current.matchAll(referencePattern)) found.push(match[1] ?? match[2])
  }
  scan(value)
  return found
}

export function renameVariable(content: WorkflowContent, oldName: string, newName: string): WorkflowContent {
  const replace = (text: string) => text.replace(referencePattern, (match, standard: string | undefined, short: string | undefined) => (standard ?? short) === oldName ? `${standard ? '$' : ''}{${newName}}` : match)
  return { ...content, document: { ...content.document,
    nodes: content.document.nodes.map(node => {
      if (localVariables(content, node.id).includes(oldName)) return node
      const config = mapReferences(node.config, oldName, newName, replace, new Set(node.literalPaths ?? [])) as WorkflowNode['config']
      if ((node.type === 'get_element_info' || node.type === 'screenshot' || node.type === 'set_variable') && config.variableName === oldName) config.variableName = newName
      return { ...node, config }
    }),
    variables: content.document.variables.map(variable => ({ ...variable, name: variable.name === oldName ? newName : variable.name, value: mapText(variable.value, replace) as typeof variable.value })),
  } }
}

export function renameLoopVariable(content: WorkflowContent, nodeId: string, field: 'indexVariable' | 'itemVariable', name: string): WorkflowContent {
  const owner = content.document.nodes.find(node => node.id === nodeId)!
  const previous = String(owner.config[field])
  const ids = new Set(blockNodes(content, nodeId))
  const replace = (text: string) => text.replace(referencePattern, (match, standard: string | undefined, short: string | undefined) => (standard ?? short) === previous ? `${standard ? '$' : ''}{${name}}` : match)
  return { ...content, document: { ...content.document, nodes: content.document.nodes.map(node => node.id === nodeId ? { ...node, config: { ...node.config, [field]: name } } : ids.has(node.id) ? { ...node, config: mapReferences(node.config, previous, name, replace, new Set(node.literalPaths ?? [])) as WorkflowNode['config'] } : node) } }
}
