import { beforeEach, expect, it } from 'vitest'
import { useWorkflowStore as store } from '../editor-store'
import { executeClientAction } from '../api/aiAssistantSkills'
beforeEach(() => { store.getState().clearWorkflow(); store.getState().addNode('open_page', { x: 0, y: 0 }); store.getState().addNode('click_element', { x: 30, y: 60 }); store.getState().markAsSaved() })
it('applies an AI batch as one reversible document edit', async () => {
  const [a, b] = store.getState().nodes
  const response = await executeClientAction('bulk_update_nodes', { patches: [{ node_id: a.id, config: { url: 'https://example.test' } }, { node_id: b.id, config: { selector: '#new' } }] })
  expect(response.success).toBe(true)
  expect(store.getState().nodes[0].data.url).toBe('https://example.test')
  expect(store.getState().nodes[1].data.selector).toBe('#new')
  expect(store.getState().hasUnsavedChanges).toBe(true)
  store.getState().undo()
  expect(store.getState().nodes.map(n => n.data)).toEqual([a.data, b.data])
  store.getState().redo()
  expect(store.getState().nodes[1].data.selector).toBe('#new')
})
it('does not mark missing-node or identical updates dirty or consume history', () => {
  const node = store.getState().nodes[0]
  const before = store.getState().history
  store.getState().updateNodeData('missing', { url: 'ignored' })
  store.getState().updateNodeData(node.id, { ...node.data })
  expect(store.getState().hasUnsavedChanges).toBe(false)
  expect(store.getState().history).toEqual(before)
})
it('merges repeated patches to one node and restores removed optional fields', () => {
  const id = store.getState().nodes[0].id
  store.getState().updateNodeData(id, { errorPolicy: { mode: 'continue' } })
  store.getState().updateNodesData([{ nodeId: id, data: { url: 'first' } }, { nodeId: id, data: { url: 'last', errorPolicy: undefined } }])
  expect(store.getState().nodes[0].data).toMatchObject({ url: 'last', errorPolicy: undefined })
  store.getState().undo()
  expect(store.getState().nodes[0].data.errorPolicy).toEqual({ mode: 'continue' })
  expect(store.getState().nodes[0].data.url).not.toBe('last')
})
it('keeps combined variable edits isolated from caller mutation and preserves selection', () => {
  const id=store.getState().nodes[0].id
  store.getState().selectNode(id)
  const variables=[{name:'items',value:[1],type:'array' as const,scope:'global' as const}]
  store.getState().updateNodesData([{nodeId:id,data:{url:'changed'}}],variables)
  variables[0].value.push(2)
  expect(store.getState().variables[0].value).toEqual([1])
  expect(store.getState().selectedNodeId).toBe(id)
  store.getState().undo()
  expect(store.getState().variables).toEqual([])
  expect(store.getState().nodes[0].data.url).not.toBe('changed')
})
it('skips an identical combined patch without consuming history or dirtying the draft', () => {
  store.getState().addVariable({name:'index',value:1,type:'number',scope:'global'})
  store.getState().markAsSaved()
  const before=store.getState(); const node=before.nodes[0]
  store.getState().updateNodesData([{nodeId:node.id,data:{...node.data}}],structuredClone(before.variables))
  expect(store.getState().history).toBe(before.history)
  expect(store.getState().hasUnsavedChanges).toBe(false)
})
