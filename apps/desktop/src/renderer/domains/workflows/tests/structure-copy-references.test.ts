import { beforeEach, expect, it } from 'vitest'
import type { Node } from '@xyflow/react'
import { useWorkflowStore as store, type NodeData } from '../editor-store'
const graph = (): Node<NodeData>[] => [
  { id: 'group', type: 'groupNode', position: { x: 200, y: 100 }, data: { moduleType: 'group', label: 'container', isSubflow: true } },
  { id: 'child', type: 'moduleNode', parentId: 'group', position: { x: 20, y: 30 }, data: { moduleType: 'print_log', label: 'child' } },
  { id: 'call', type: 'moduleNode', position: { x: 600, y: 100 }, data: { moduleType: 'subflow', label: 'call', subflowGroupId: 'group', errorPolicy: { mode: 'retry-from', targetId: 'child', maxRetries: 2 } } },
]
const edges = [{ id: 'edge', source: 'child', target: 'call' }]
const documentNodes = (nodes: Node<NodeData>[]) => nodes.map(({ selected: _selected, ...node }) => node)
beforeEach(() => store.getState().clearWorkflow())
it.each(['internal', 'system', 'merge'] as const)('%s remaps internal container/subflow/retry references with node identities and keeps relative child position', mode => {
  const nodes = graph()
  if (mode === 'internal') {
    store.getState().setGraph(nodes, edges)
    store.getState().copyNodes(nodes.map(n => n.id)); store.getState().pasteNodes({ x: 800, y: 500 })
  } else if (mode === 'system') store.getState().pasteNodesFromClipboard(nodes, edges, { x: 800, y: 500 })
  else expect(store.getState().mergeWorkflow(JSON.stringify({ nodes, edges, variables: [] }), { x: 800, y: 500 })).toBe(true)
  const pasted = store.getState().nodes.slice(-3)
  const [group, child, call] = pasted
  expect(group.id).not.toBe('group')
  expect(child.parentId).toBe(group.id)
  expect(child.position).toEqual({ x: 20, y: 30 })
  expect(call.data.subflowGroupId).toBe(group.id)
  expect(call.data.errorPolicy?.targetId).toBe(child.id)
  expect(store.getState().edges.at(-1)).toMatchObject({ source: child.id, target: call.id })
  const json = store.getState().exportWorkflow()
  store.getState().undo(); expect(store.getState().nodes.length).toBe(mode === 'internal' ? 3 : 0)
  store.getState().redo(); expect(documentNodes(store.getState().nodes.slice(-3))).toEqual(documentNodes(pasted))
  store.getState().clearWorkflow(); expect(store.getState().importWorkflow(json)).toBe(true)
  expect(documentNodes(store.getState().nodes.slice(-3))).toEqual(documentNodes(pasted))
  expect(nodes).toEqual(graph())
})
