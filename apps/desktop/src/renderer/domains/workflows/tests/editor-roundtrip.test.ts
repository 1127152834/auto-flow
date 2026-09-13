import { beforeEach, expect, it } from 'vitest'
import { useWorkflowStore } from '../editor-store'
import { snapshotKey } from '../lib/snapshotKey'
beforeEach(()=>useWorkflowStore.getState().clearWorkflow())
it('keeps source node configuration and positions through copy, undo and JSON roundtrip',()=>{
  const store=useWorkflowStore.getState()
  store.addNode('open_page',{x:100,y:200})
  const node=useWorkflowStore.getState().nodes[0]
  useWorkflowStore.getState().updateNodeData(node.id,{url:'https://example.test/',label:'Open fixture'})
  const content=useWorkflowStore.getState().exportWorkflow()
  useWorkflowStore.getState().clearWorkflow()
  expect(useWorkflowStore.getState().importWorkflow(content)).toBe(true)
  expect(useWorkflowStore.getState().nodes[0]).toMatchObject({id:node.id,position:{x:100,y:200},data:{url:'https://example.test/'}})
  useWorkflowStore.getState().addNode('click_element',{x:100,y:400})
  expect(useWorkflowStore.getState().nodes).toHaveLength(2)
  useWorkflowStore.getState().undo();expect(useWorkflowStore.getState().nodes).toHaveLength(1)
  useWorkflowStore.getState().redo();expect(useWorkflowStore.getState().nodes).toHaveLength(2)
})
it('acknowledges save timestamps and selection changes but detects newer content and layout',()=>{
  const doc={name:'a',nodes:[{id:'n',position:{x:1,y:2},data:{text:'a'},selected:false}],createdAt:'one',updatedAt:'one'}
  expect(snapshotKey(JSON.stringify(doc))).toBe(snapshotKey(JSON.stringify({...doc,updatedAt:'two',nodes:[{...doc.nodes[0],selected:true}]})))
  expect(snapshotKey(JSON.stringify(doc))).not.toBe(snapshotKey(JSON.stringify({...doc,name:'new draft'})))
  expect(snapshotKey(JSON.stringify(doc))).not.toBe(snapshotKey(JSON.stringify({...doc,nodes:[{...doc.nodes[0],position:{x:10,y:20}}]})))
})

it('does not turn React Flow measurements and selection into edits or consume undo/redo history', () => {
  const store = useWorkflowStore.getState()
  store.clearWorkflow()
  store.addNode('open_page', { x: 0, y: 0 })
  store.addNode('click_element', { x: 200, y: 0 })
  const [first, second] = useWorkflowStore.getState().nodes
  store.markAsSaved()
  const historyIndex = useWorkflowStore.getState().historyIndex
  store.onNodesChange([{ type: 'dimensions', id: second.id, dimensions: { width: 160, height: 50 } }, { type: 'select', id: second.id, selected: true }])
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(false)
  expect(useWorkflowStore.getState().historyIndex).toBe(historyIndex)
  store.undo()
  expect(useWorkflowStore.getState().nodes.map(node => node.id)).toEqual([first.id])
  store.onNodesChange([{ type: 'dimensions', id: first.id, dimensions: { width: 160, height: 50 } }])
  store.redo()
  expect(useWorkflowStore.getState().nodes.map(node => node.id)).toEqual([first.id, second.id])
})
it('reports the first live edit as undoable and never redoes over a new branch', () => {
  const store = useWorkflowStore.getState()
  store.addNode('open_page', { x: 0, y: 0 })
  expect(store.canUndo()).toBe(true)
  store.undo()
  expect(store.canRedo()).toBe(true)
  store.addNode('click_element', { x: 0, y: 0 })
  expect(store.canRedo()).toBe(false)
  store.redo()
  expect(useWorkflowStore.getState().nodes[0].data.moduleType).toBe('click_element')
})

it('undoes a multi-event drag in one step and preserves the final position for redo', () => {
  const store = useWorkflowStore.getState()
  store.addNode('open_page', { x: 10, y: 20 })
  const id = useWorkflowStore.getState().nodes[0].id
  store.markAsSaved()
  store.onNodesChange([{ type: 'position', id, position: { x: 30, y: 40 }, dragging: true }])
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
  store.onNodesChange([{ type: 'position', id, position: { x: 60, y: 80 }, dragging: true }])
  store.onNodesChange([{ type: 'position', id, position: { x: 60, y: 80 }, dragging: false }])
  store.undo()
  expect(useWorkflowStore.getState().nodes[0].position).toEqual({ x: 10, y: 20 })
  store.redo()
  expect(useWorkflowStore.getState().nodes[0].position).toEqual({ x: 60, y: 80 })
})
it('treats position updates without a drag flag as editable keyboard movement', () => {
  const store = useWorkflowStore.getState()
  store.addNode('open_page', { x: 10, y: 20 })
  store.markAsSaved()
  store.onNodesChange([{ type: 'position', id: useWorkflowStore.getState().nodes[0].id, position: { x: 20, y: 20 } }])
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
  store.undo()
  expect(useWorkflowStore.getState().nodes[0].position).toEqual({ x: 10, y: 20 })
})
it('undoes an explicit multi-event resize as one edit', () => {
  const store = useWorkflowStore.getState()
  store.addNode('open_page', { x: 0, y: 0 })
  const id = useWorkflowStore.getState().nodes[0].id
  store.onNodesChange([{ type: 'dimensions', id, dimensions: { width: 300, height: 100 }, setAttributes: true, resizing: true }])
  store.onNodesChange([{ type: 'dimensions', id, dimensions: { width: 400, height: 200 }, setAttributes: true, resizing: true }])
  store.onNodesChange([{ type: 'dimensions', id, dimensions: { width: 400, height: 200 }, setAttributes: true, resizing: false }])
  store.undo()
  expect(useWorkflowStore.getState().nodes[0].width).toBeUndefined()
  store.redo()
  expect(useWorkflowStore.getState().nodes[0]).toMatchObject({ width: 400, height: 200 })
})
