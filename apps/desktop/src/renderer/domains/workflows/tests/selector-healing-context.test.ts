import {beforeEach,expect,it,vi} from 'vitest'
import {useWorkflowStore as store} from '../editor-store'
import {reviewSelectorHeals} from '../lib/selectorHealing'
beforeEach(()=>{store.getState().clearWorkflow();store.getState().addNode('click_element',{x:0,y:0});store.getState().updateNodeData(store.getState().nodes[0].id,{selector:'#old'});store.getState().markAsSaved()})
function detail(){return {workflowId:'server-workflow',documentId:store.getState().id,heals:[{nodeId:store.getState().nodes[0].id,oldSelector:'#old',newSelector:'#new',configKey:'selector'}]}}
it('applies the reviewed batch in one reversible edit',async()=>{
 const id=store.getState().nodes[0].id
 store.getState().addNode('click_element',{x:10,y:0});const second=store.getState().nodes[1].id;store.getState().updateNodeData(second,{selector:'#two'});store.getState().markAsSaved()
 const data=detail();data.heals.push({nodeId:second,oldSelector:'#two',newSelector:'#second',configKey:'selector'})
 await reviewSelectorHeals(data,async()=>true)
 expect(store.getState().nodes.map(n=>n.data.selector)).toEqual(['#new','#second'])
 store.getState().undo();expect(store.getState().nodes.map(n=>n.data.selector)).toEqual(['#old','#two'])
 store.getState().redo();expect(store.getState().nodes.find(n=>n.id===id)?.data.selector).toBe('#new')
})
it.each(['document','field','delete','unmount'])('does not apply a confirmed stale result after %s',async change=>{
 let release!:(value:boolean)=>void;let active=true;const data=detail();const pending=reviewSelectorHeals(data,()=>new Promise(resolve=>{release=resolve}),()=>active)
 if(change==='document'){const nodes=store.getState().nodes;store.getState().clearWorkflow();store.setState({nodes})}
 if(change==='field')store.getState().updateNodeData(data.heals[0].nodeId,{selector:'#manual'})
 if(change==='delete')store.getState().deleteNode(data.heals[0].nodeId)
 if(change==='unmount')active=false
 release(true);await pending
 expect(store.getState().nodes.some(n=>n.data.selector==='#new')).toBe(false)
 expect(store.getState().logs.some(l=>l.level==='success'&&l.message.includes('已写回'))).toBe(false)
})
it('preserves the draft when declined',async()=>{await reviewSelectorHeals(detail(),async()=>false);expect(store.getState().nodes[0].data.selector).toBe('#old');expect(store.getState().hasUnsavedChanges).toBe(false)})
it.each(['foreign','missing-old','already-edited','invalid-key','duplicate'])('rejects %s before asking to write',async kind=>{
 const data=detail();if(kind==='foreign')data.documentId='another';if(kind==='missing-old')data.heals[0].oldSelector=undefined as unknown as string;if(kind==='already-edited')store.getState().updateNodeData(data.heals[0].nodeId,{selector:'#manual'});if(kind==='invalid-key')data.heals[0].configKey='__proto__';if(kind==='duplicate')data.heals.push({...data.heals[0]});const confirm=vi.fn(async()=>true)
 await reviewSelectorHeals(data,confirm);expect(confirm).not.toHaveBeenCalled();expect(store.getState().nodes[0].data.selector).not.toBe('#new')
})
