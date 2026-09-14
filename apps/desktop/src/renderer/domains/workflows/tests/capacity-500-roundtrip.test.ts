import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { beforeEach, expect, it } from 'vitest'
import { useWorkflowStore as store } from '../editor-store'
import { parseGraphToBlocks, generateGraphFromBlocks } from '../components/blockFlowModel'
const fixture = JSON.parse(readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), '../../../../../../../docs/migration/studio-frontend-completion/fixtures/capacity-500.bundle.json'), 'utf8')).workflow
beforeEach(() => { store.getState().clearWorkflow(); expect(store.getState().importWorkflow(structuredClone(fixture))).toBe(true) })
it('imports all 500 nodes and 499 links without truncation', () => {
  expect(store.getState().nodes).toHaveLength(500); expect(store.getState().edges).toHaveLength(499)
  for (let i = 0; i < 500; i++) expect(store.getState().nodes[i]).toMatchObject({ id: fixture.nodes[i].id, data: fixture.nodes[i].data, position: fixture.nodes[i].position })
  expect(store.getState().edges).toEqual(fixture.edges)
})
it('preserves all content and layout through serialization and reopening', () => {
  const before = structuredClone({ nodes: store.getState().nodes, edges: store.getState().edges })
  const serialized = store.getState().exportWorkflow()
  store.getState().clearWorkflow(); expect(store.getState().importWorkflow(serialized)).toBe(true)
  expect(store.getState().nodes).toEqual(before.nodes); expect(store.getState().edges).toEqual(before.edges)
})
it('undoes and redoes a final-node change without touching earlier nodes', () => {
  const before = structuredClone(store.getState().nodes)
  store.getState().updateNodeData('capacity-node-0500', { logMessage: '容量末尾修改' })
  expect(store.getState().nodes.slice(0, 499)).toEqual(before.slice(0, 499))
  expect(store.getState().nodes[499].data.logMessage).toBe('容量末尾修改')
  store.getState().undo(); expect(store.getState().nodes).toEqual(before)
  store.getState().redo(); expect(store.getState().nodes[499].data.logMessage).toBe('容量末尾修改')
})
it('keeps all actions and chain order through the block-view model', () => {
  const before = store.getState()
  const blocks = parseGraphToBlocks(before.nodes, before.edges)
  expect(blocks).toHaveLength(500)
  const graph = generateGraphFromBlocks(blocks)
  expect(graph.nodes).toHaveLength(500); expect(graph.edges).toHaveLength(499)
  for (const node of before.nodes) expect(graph.nodes.find(item => item.id === node.id)?.data).toMatchObject(node.data)
  // Edge array order is not execution order; follow the actual directed chain.
  let current = 'capacity-node-0001'
  const visited: string[] = []
  for (let i = 0; i < 500; i++) {
    visited.push(current)
    const outgoing = graph.edges.filter(edge => edge.source === current)
    expect(outgoing).toHaveLength(i === 499 ? 0 : 1)
    if (outgoing[0]) current = outgoing[0].target
  }
  expect(visited).toEqual(fixture.nodes.map((node: {id: string}) => node.id))
})
