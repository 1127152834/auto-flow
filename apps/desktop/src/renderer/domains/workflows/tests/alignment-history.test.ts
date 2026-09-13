import { beforeEach, expect, it } from 'vitest'
import { useWorkflowStore as store } from '../editor-store'

beforeEach(() => {
  store.getState().clearWorkflow()
  for (let i = 0; i < 3; i++) store.getState().addNode('open_page', { x: i * 100, y: i * 100 })
  store.setState(state => ({ nodes: state.nodes.map((node, i) => ({ ...node, selected: i < 2, ...(i === 0 ? { height: 180 } : { measured: { height: 20 } }) })) }))
  store.getState().markAsSaved()
})
it('aligns bottom edges with different measured heights and supports one undo/redo', () => {
  const before = store.getState().nodes
  store.getState().alignNodes('bottom')
  const after = store.getState().nodes
  expect(after[0].position.y + 180).toBe(after[1].position.y + 20)
  expect(after[2]).toEqual(before[2])
  expect(store.getState().hasUnsavedChanges).toBe(true)
  store.getState().undo()
  expect(store.getState().nodes.map(n => n.position)).toEqual(before.map(n => n.position))
  store.getState().redo()
  expect(store.getState().nodes.map(n => n.position)).toEqual(after.map(n => n.position))
})
it.each(['distribute-horizontal', 'distribute-vertical'] as const)('does not consume history for %s with only two selected nodes', type => {
  const id = store.getState().nodes[0].id
  const old = store.getState().nodes[0].data.label
  store.getState().updateNodeData(id, { label: '上一个真实编辑' })
  store.getState().alignNodes(type)
  store.getState().undo()
  expect(store.getState().nodes[0].data.label).toBe(old)
})
