import {beforeEach, expect, it} from 'vitest'
import {useWorkflowStore} from '../editor-store'

beforeEach(()=>useWorkflowStore.getState().clearWorkflow())
it('new documents persist node ownership while later navigations reuse the instance',()=>{
 const store=useWorkflowStore.getState()
 store.addNode('open_page',{x:0,y:0})
 store.addNode('open_page',{x:0,y:100})
 const document=JSON.parse(store.exportWorkflow())
 expect(document.browserEnvironmentVersion).toBe(1)
 expect(document.schemaVersion).toBe(3)
 expect(document.nodes.map((node:{data:{browserEnvironment:{source:string}}})=>node.data.browserEnvironment.source)).toEqual(['profile','profile'])
 store.clearWorkflow();store.importWorkflow(document)
 expect(JSON.parse(store.exportWorkflow()).browserEnvironmentVersion).toBe(1)
})
it('legacy import and save stay legacy; explicit migration can be undone',()=>{
 const store=useWorkflowStore.getState()
 store.importWorkflow({id:'old',name:'old',nodes:[{id:'a',type:'open_page',position:{x:0,y:0},data:{moduleType:'open_page',url:'https://test'}}],edges:[],variables:[]})
 expect(JSON.parse(store.exportWorkflow()).browserEnvironmentVersion).toBeUndefined()
 store.migrateBrowserEnvironment('a',{source:'newFromProfile',profileId:'template'})
 expect(JSON.parse(store.exportWorkflow()).nodes[0].data.browserEnvironment.profileId).toBe('template')
 store.undo()
 expect(JSON.parse(store.exportWorkflow()).browserEnvironmentVersion).toBeUndefined()
 store.redo()
 expect(JSON.parse(store.exportWorkflow()).browserEnvironmentVersion).toBe(1)
})

import {act,cleanup,render,screen,waitFor} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {afterEach,vi} from 'vitest'
import {choiceTestEnvironment} from '../../../shared/testing/choice-user'
import {BrowserEnvironmentFields} from '../components/config-panels/BrowserEnvironmentFields'
import * as api from '../api'
import {Toolbar} from '../components/Toolbar'
vi.hoisted(()=>{const data=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value),removeItem:(key:string)=>data.delete(key)})})
choiceTestEnvironment()
async function chooseOption(user:ReturnType<typeof userEvent.setup>,control:HTMLElement,name:string){control.focus();await user.keyboard('{ArrowDown}');await user.click(await screen.findByRole('option',{name}))}
afterEach(()=>{cleanup();vi.restoreAllMocks()})
function Fields(){const node=useWorkflowStore(state=>state.nodes[0]);return <BrowserEnvironmentFields data={node.data} onChange={(key,value)=>useWorkflowStore.getState().updateNodeData(node.id,{[key]:value})}/>}
it('edits node template proxy and installed kernel without changing global selection',async()=>{
 vi.spyOn(api.browserApi,'profiles').mockResolvedValue({success:true,data:{items:[{id:'one',name:'模板一'}] as never,total:1}})
 vi.spyOn(api,'apiRequest').mockImplementation(async path=>({success:true,data:path.includes('kernels')?{items:[{edition:'public',version:'145'}]}:{proxies:[{id:'proxy-one',name:'代理一',enabled:true}],pools:[]}}) as never)
 act(()=>{const store=useWorkflowStore.getState();store.addNode('open_page',{x:0,y:0});store.selectNode(useWorkflowStore.getState().nodes[0].id)})
 render(<Fields/>)
 const user=userEvent.setup()
 await waitFor(()=>expect(screen.getByLabelText('浏览器配置')).toBeTruthy())
 await chooseOption(user,screen.getByLabelText('浏览器配置'),'模板一')
 await chooseOption(user,screen.getByLabelText('代理'),'指定代理')
 await chooseOption(user,screen.getByLabelText('指定代理'),'代理一')
 await chooseOption(user,screen.getByLabelText('浏览器内核'),'公开版 145')
 expect(useWorkflowStore.getState().nodes[0].data.browserEnvironment).toEqual({source:'profile',profileId:'one',proxy:{mode:'fixed',proxyId:'proxy-one'},kernel:{edition:'public',version:'145'}})
 const exported=useWorkflowStore.getState().exportWorkflow()
 act(()=>{useWorkflowStore.getState().clearWorkflow();useWorkflowStore.getState().importWorkflow(exported)})
 expect(screen.getByLabelText('浏览器内核').textContent).toContain('公开版 145')
 expect(screen.queryByLabelText('环境来源')).toBeNull()
 await chooseOption(user,screen.getByLabelText('代理'),'沿用浏览器配置')
 expect(screen.queryByRole('option',{name:'使用代理池'})).toBeNull()
})
it('removes the toolbar browser selector',()=>{render(<Toolbar/>);expect(screen.queryByLabelText('运行浏览器配置')).toBeNull()})
it('inspection rejects an old global choice when no initialization node is selected',async()=>{
 const global=await import('../hooks/stores/globalConfigStore')
 global.useGlobalConfigStore.getState().setBrowserProfileId('old-global')
 expect(await api.browserApi.resolveNodeBrowser()).toMatchObject({success:false})
 global.useGlobalConfigStore.getState().setBrowserProfileId('')
})
it('does not merge browser nodes across incompatible document contracts',()=>{
 const store=useWorkflowStore.getState()
 const legacy={name:'legacy',nodes:[{id:'a',type:'open_page',position:{x:0,y:0},data:{moduleType:'open_page'}}],edges:[]}
 expect(store.mergeWorkflow(JSON.stringify(legacy))).toBe(false)
 expect(useWorkflowStore.getState().nodes).toEqual([])
})
it('browserless execution does not depend on template catalogs',async()=>{
 const profiles=vi.spyOn(api.browserApi,'profiles').mockResolvedValue({success:false,error:'offline'})
 expect(await api.browserApi.validateNodeResources([{id:'wait',data:{moduleType:'wait'}}])).toEqual({success:true})
 expect(profiles).not.toHaveBeenCalled()
})
it('inspection refuses node configuration edited while its catalog is loading',async()=>{
 const store=useWorkflowStore.getState();store.addNode('open_page',{x:0,y:0},{browserEnvironment:{source:'newFromProfile',profileId:'one'}});store.selectNode(useWorkflowStore.getState().nodes[0].id)
 let release!:(value:Awaited<ReturnType<typeof api.browserApi.profiles>>)=>void
 vi.spyOn(api.browserApi,'profiles').mockImplementation(()=>new Promise(resolve=>{release=resolve}))
 vi.spyOn(api.projectResourceApi,'defaults').mockResolvedValue({success:true,data:null})
 const pending=api.browserApi.resolveNodeBrowser()
 store.updateNodeData(useWorkflowStore.getState().nodes[0].id,{browserEnvironment:{source:'newFromProfile',profileId:'two'}})
 release({success:true,data:{items:[{id:'one',name:'one'}] as never,total:1}})
 expect(await pending).toMatchObject({success:false,error:expect.stringContaining('变更')})
})

it('requires an explicit browser profile even when the project has a default',async()=>{
 vi.spyOn(api.browserApi,'profiles').mockResolvedValue({success:true,data:{items:[{id:'one',name:'配置一'}] as never,total:1}})
 vi.spyOn(api.projectResourceApi,'defaults').mockResolvedValue({success:true,data:{profileId:'one',proxy:{mode:'sourceDefault'},modelProviderId:null}})
 expect(await api.browserApi.validateNodeResources([{id:'open',data:{moduleType:'open_page',browserEnvironment:{source:'profile'}}}])).toMatchObject({success:false,data:{nodeId:'open'}})
})
