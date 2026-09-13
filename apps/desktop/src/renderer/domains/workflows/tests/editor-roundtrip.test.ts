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
