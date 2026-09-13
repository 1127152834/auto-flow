import { beforeEach, expect, it } from 'vitest'
import { useWorkflowStore as store } from '../editor-store'
beforeEach(() => { store.getState().clearWorkflow(); store.getState().addNode('open_page', { x: 0, y: 0 }); store.getState().addNode('click_element', { x: 0, y: 100 }); store.getState().markAsSaved() })
it.each(['add', 'delete', 'connect'] as const)('marks %s as unsaved and supports undo/redo', action => {
  const before = store.getState()
  if (action === 'add') store.getState().addNode('input_text', { x: 0, y: 200 })
  if (action === 'delete') store.getState().deleteNode(before.nodes[0].id)
  if (action === 'connect') store.getState().onConnect({ source: before.nodes[0].id, target: before.nodes[1].id, sourceHandle: null, targetHandle: null })
  const after = store.getState()
  expect(after.hasUnsavedChanges).toBe(true)
  store.getState().undo()
  expect(store.getState().nodes.map(n => n.id)).toEqual(before.nodes.map(n => n.id))
  expect(store.getState().edges).toEqual(before.edges)
  store.getState().redo()
  expect(store.getState().nodes.map(n => n.id)).toEqual(after.nodes.map(n => n.id))
  expect(store.getState().edges).toEqual(after.edges)
})
it.each(['missing-delete', 'self-link', 'duplicate-link'] as const)('does not mark %s as an unsaved graph edit', action => {
  const [a, b] = store.getState().nodes
  const connection = { source: a.id, target: b.id, sourceHandle: null, targetHandle: null }
  if (action === 'duplicate-link') { store.getState().onConnect(connection); store.getState().markAsSaved() }
  const before = store.getState()
  if (action === 'missing-delete') store.getState().deleteNode('absent')
  if (action === 'self-link') store.getState().onConnect({ ...connection, target: a.id })
  if (action === 'duplicate-link') store.getState().onConnect(connection)
  expect(store.getState().hasUnsavedChanges).toBe(false)
  expect(store.getState().nodes).toEqual(before.nodes)
  expect(store.getState().edges).toEqual(before.edges)
  expect(store.getState().history).toEqual(before.history)
})
