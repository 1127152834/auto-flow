// Remediation M2 R2-29 / AC2-17: which node outputs a node can rely on.
// Output declarations come from the backend (generated executor schema). An output is "required"
// when every path from the start to the node passes the producing node successfully; reachable
// outputs that some path skips (another branch, zero loop iterations, an error branch) are
// "conditional" and must be checked for empty values. References use stable identities:
// {node.<nodeId>.<outputKey>} keeps working when the node or its variable is renamed.
import schema from '../generated/executor-config-keys.json'
import { getModuleDefaultVar } from './moduleDefaultVars'

type OutputDeclaration = { key: string; name: string; sensitive: boolean; availability: 'afterSuccess' | 'loopBody' }
type GraphNode = { id: string; data?: unknown }
type GraphEdge = { source: string; target: string; sourceHandle?: string | null }
export type AvailableOutput = {
  nodeId: string; key: string; name: string; label: string; variable: string
  reference: string; required: boolean; sensitive: boolean; named: boolean
}

const declarations = schema.nodes as Record<string, { outputs?: OutputDeclaration[] }>
const LOOP_TYPES = new Set(['loop', 'foreach', 'foreach_dict', 'infinite_loop'])
const CANVAS_ONLY = new Set(['group', 'note'])
const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)
const configOf = (data: Record<string, unknown>) => isRecord(data.config) ? { ...data, ...data.config } : data

export function declaredOutputs(moduleType: string): OutputDeclaration[] {
  return declarations[moduleType]?.outputs ?? []
}

export function nodeOutputReference(nodeId: string, key: string) {
  return `node.${nodeId}.${key}`
}

/** Pseudo graph: a node's success is a separate point, loops split into "body" and "done". */
function pseudoGraph(nodes: GraphNode[], edges: GraphEdge[]) {
  const types = new Map(nodes.flatMap(node => isRecord(node.data) && !CANVAS_ONLY.has(String(node.data.moduleType)) ? [[node.id, String(node.data.moduleType)]] : []))
  const successors = new Map<string, Set<string>>()
  const link = (from: string, to: string) => { if (!successors.has(from)) successors.set(from, new Set()); successors.get(from)!.add(to) }
  for (const [id, type] of types) {
    if (LOOP_TYPES.has(type)) { link(id, `${id}#body`); link(id, `${id}#done`) } else link(id, `${id}#ok`)
  }
  const incoming = new Set<string>()
  for (const edge of edges) {
    if (!types.has(edge.source) || !types.has(edge.target)) continue
    incoming.add(edge.target)
    const loop = LOOP_TYPES.has(types.get(edge.source)!)
    const handle = edge.sourceHandle ?? ''
    const from = handle === 'error' ? edge.source
      : loop ? (handle === 'loop' || handle === 'loop-body' ? `${edge.source}#body` : `${edge.source}#done`)
      : `${edge.source}#ok`
    link(from, edge.target)
  }
  for (const id of types.keys()) if (!incoming.has(id)) link('#start', id)
  // A loop body returns to its loop when it ends, so its values (and the loop variables) may be
  // visible after the loop — but never on the path where the body ran zero times.
  for (const [id, type] of types) {
    if (!LOOP_TYPES.has(type)) continue
    link(`${id}#body`, `${id}#done`)
    for (const point of reachableFrom(`${id}#body`, successors)) {
      if (point.endsWith('#ok') && !(successors.get(point)?.size)) link(point, `${id}#done`)
    }
  }
  return { types, successors }
}

function reachableFrom(start: string, successors: Map<string, Set<string>>) {
  const seen = new Set<string>([start]), queue = [start]
  while (queue.length) for (const next of successors.get(queue.shift()!) ?? []) if (!seen.has(next)) { seen.add(next); queue.push(next) }
  return seen
}

function dominators(successors: Map<string, Set<string>>) {
  const reachable = reachableFrom('#start', successors)
  const predecessors = new Map<string, string[]>()
  for (const [from, targets] of successors) if (reachable.has(from)) for (const to of targets) predecessors.set(to, [...(predecessors.get(to) ?? []), from])
  const dom = new Map<string, Set<string>>([...reachable].map(point => [point, point === '#start' ? new Set(['#start']) : new Set(reachable)]))
  for (let changed = true; changed;) {
    changed = false
    for (const point of reachable) {
      if (point === '#start') continue
      const sets = (predecessors.get(point) ?? []).map(item => dom.get(item)!)
      const next = new Set([point, ...(sets.length ? [...sets[0]].filter(item => sets.every(set => set.has(item))) : [])])
      if (next.size !== dom.get(point)!.size) { dom.set(point, next); changed = true }
    }
  }
  return dom
}

/** Outputs of other nodes that can have run before `targetId`, each marked required or conditional. */
export function outputAvailability(nodes: GraphNode[], edges: GraphEdge[], targetId: string): AvailableOutput[] {
  const { types, successors } = pseudoGraph(nodes, edges)
  if (!types.has(targetId)) return []
  const dom = dominators(successors).get(targetId) ?? new Set<string>()
  const result: AvailableOutput[] = []
  for (const node of nodes) {
    const type = types.get(node.id)
    if (!type || node.id === targetId || !isRecord(node.data)) continue
    const config = configOf(node.data)
    for (const output of declaredOutputs(type)) {
      const producer = output.availability === 'loopBody' ? `${node.id}#body` : LOOP_TYPES.has(type) ? `${node.id}#done` : `${node.id}#ok`
      if (!reachableFrom(producer, successors).has(targetId)) continue
      const explicit = typeof config[output.key] === 'string' ? String(config[output.key]).trim() : ''
      // Unnamed outputs get the editor's default name (or a readable fallback) when first referenced.
      const variable = explicit || getModuleDefaultVar(type, output.key) || `${type}_${output.key}`
      result.push({
        nodeId: node.id, key: output.key, name: output.name, variable, named: Boolean(explicit),
        label: String(node.data.label || node.data.name || type), reference: nodeOutputReference(node.id, output.key),
        required: dom.has(producer), sensitive: output.sensitive,
      })
    }
  }
  return result
}
