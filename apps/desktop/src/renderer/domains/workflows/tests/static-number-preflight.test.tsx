import {act,cleanup,fireEvent,render,waitFor} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
vi.hoisted(() => {
 const values = new Map<string, string>()
 vi.stubGlobal('localStorage', { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key) })
})
import {useWorkflowStore as store} from '../editor-store'
import {staticNumberIssues} from '../lib/staticNumberPreflight'
import {moduleCategories} from '../components/ModuleSidebar'
import {Toolbar} from '../components/Toolbar'
import {workflowApi} from '../api'
import {emitAssistantUiEvent} from '../api/aiAssistantSkills'
beforeEach(()=>store.getState().clearWorkflow())
afterEach(()=>{cleanup();vi.restoreAllMocks()})
function node(type='wait',data:Record<string,unknown>={}){
 store.getState().addNode(type as 'wait',{x:0,y:0},data)
 return store.getState().nodes.at(-1)!
}
it.each(['1abc','Infinity','1e999','',-1,true])('rejects static wait duration %j without mutating its saved text',value=>{
 const n=node('wait',{duration:value});expect(staticNumberIssues(store.getState().nodes)).toEqual([{nodeId:n.id,path:'data.duration',message:expect.any(String)}]);expect(n.data.duration).toBe(value)
})
it.each([0,0.5,'1e2','+2','{duration}','${duration}',undefined])('allows finite or deferred duration %j',duration=>{
 node('wait',{duration});expect(staticNumberIssues(store.getState().nodes)).toEqual([])
})
it.each([['timeout','bad'],['retryCount',1.5],['retryCount',11],['retryCount',-1],['retryDelay','bad']])('locates invalid common field %s', (field,value)=>{
 const n=node('open_page',{retryCount:2,[field]:value});expect(staticNumberIssues(store.getState().nodes)).toContainEqual({nodeId:n.id,path:`data.${field}`,message:expect.any(String)})
})
it('does not validate disabled nodes or inactive duration/retry-delay branches',()=>{
 node('wait',{duration:'invalid',disabled:true});node('wait',{waitType:'selector',duration:'invalid',retryCount:0,retryDelay:'invalid'})
 expect(staticNumberIssues(store.getState().nodes)).toEqual([])
})
it('honors the frozen outer-timeout exceptions',()=>{
 for(const type of ['loop','foreach','scheduled_task','subflow','view_image','input_prompt','run_workflow_file'])node(type,{timeout:'ignored'})
 expect(staticNumberIssues(store.getState().nodes)).toEqual([])
})
it('does not reject any retained catalog entry defaults for these numeric rules',()=>{
 for(const type of moduleCategories.flatMap(c=>c.modules)){
  store.getState().clearWorkflow();node(type)
  expect(staticNumberIssues(store.getState().nodes),type).toEqual([])
 }
})
it.each(['keyboard','from-node','assistant-headless'])('rejects an unselected invalid node before any requests via %s',async mode=>{
 const invalid=node('wait',{duration:'1abc'});const other=node('open_page');store.getState().selectNode(other.id)
 const create=vi.spyOn(workflowApi,'create').mockResolvedValue({success:true,data:{id:'test'}})
 const execute=vi.spyOn(workflowApi,'execute').mockResolvedValue({success:true})
 const update=vi.spyOn(workflowApi,'update').mockResolvedValue({success:true})
 render(<Toolbar/>);await act(async()=>{
  if(mode==='keyboard')fireEvent.keyDown(window,{key:'F5'})
  if(mode==='from-node')window.dispatchEvent(new CustomEvent('run-from-node',{detail:{nodeId:invalid.id}}))
  if(mode==='assistant-headless')emitAssistantUiEvent('run_workflow',{headless:true})
 })
 expect(create).not.toHaveBeenCalled();expect(update).not.toHaveBeenCalled();expect(execute).not.toHaveBeenCalled()
 expect(store.getState().logs.some(log=>log.message.includes('data.duration'))).toBe(true)
 expect(store.getState().selectedNodeId).toBe(invalid.id)
 act(()=>store.getState().updateNodeData(invalid.id,{duration:1}))
 fireEvent.keyDown(window,{key:'F5'});await waitFor(()=>expect(execute).toHaveBeenCalledOnce())
})

it('does not block direct start with an invalid skipped upstream node',async()=>{
 const upstream=node('wait',{duration:'invalid'});const start=node('open_page')
 store.getState().onConnect({source:upstream.id,target:start.id,sourceHandle:null,targetHandle:null})
 const create=vi.spyOn(workflowApi,'create').mockResolvedValue({success:true,data:{id:'direct'}})
 const execute=vi.spyOn(workflowApi,'execute').mockResolvedValue({success:true})
 render(<Toolbar/>);await act(async()=>window.dispatchEvent(new CustomEvent('run-from-node',{detail:{nodeId:start.id}})))
 await waitFor(()=>expect(execute).toHaveBeenCalledWith(store.getState().id,expect.objectContaining({startNodeId:start.id,document:expect.objectContaining({nodes:expect.any(Array)})})))
 expect(create).not.toHaveBeenCalled()
})
it('checks all reachable branches and terminates on a cycle',()=>{
 const start=node('open_page');const invalid=node('wait',{duration:'bad'})
 const edges=[{id:'out',source:start.id,target:invalid.id},{id:'back',source:invalid.id,target:start.id}]
 expect(staticNumberIssues(store.getState().nodes,edges,start.id)).toMatchObject([{nodeId:invalid.id,path:'data.duration'}])
})
it('reads the current draft when a programmatic edit and run happen in the same turn',async()=>{
 const target=node('wait',{duration:1});const create=vi.spyOn(workflowApi,'create')
 render(<Toolbar/>);await act(async()=>{
  store.getState().updateNodeData(target.id,{duration:'bad'})
  window.dispatchEvent(new CustomEvent('hotkey:run'))
 })
 expect(create).not.toHaveBeenCalled();expect(store.getState().logs.some(log=>log.message.includes('data.duration'))).toBe(true)
})
