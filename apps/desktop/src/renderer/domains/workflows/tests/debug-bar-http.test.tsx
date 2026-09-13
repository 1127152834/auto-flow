import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {DebugBar} from '../components/DebugBar'
import {socketService} from '../events'
import {useWorkflowStore} from '../editor-store'
import {useDebugStore} from '../hooks/stores/debugStore'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
afterEach(()=>{cleanup();socketService.disconnect();useDebugStore.getState().clearPaused();vi.unstubAllGlobals()})
it.each([false,true])('controls a real HTTP fixture and rejects foreign pause events; lostResponse=%s',async lostResponse=>{
 vi.resetModules()
 const {mockRequest,configureMock,mockSnapshot,emitMockEvent}=await import('../api/mock-server')
 const storage=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>storage.get(key)??null,setItem:(key:string,value:string)=>storage.set(key,value)})
 let stepRequests=0
 const server=await startHttpStudioFixture((input,init)=>{
  if((input as Request).url.endsWith('/debug/step'))stepRequests++
  return mockRequest(input,init)
 })
 const restore=configureStudioConnection(server.origin,fetch)
 const post=(path:string,body:unknown)=>fetch(`${server.origin}/api${path}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
 try{
  render(<DebugBar />);socketService.connect()
  await waitFor(()=>expect(socketService.isConnected()).toBe(true))
  await post('/workflows',{id:'debug-http',name:'调试请求HTTP',nodes:[{id:'first',type:'open_page',data:{label:'真实HTTP首次暂停'}},{id:'next',type:'open_page',data:{label:'真实HTTP下一步'}}],variables:[]})
  await post('/workflows/debug-http/execute',{breakpoints:['first']})
  await screen.findByText('@ 真实HTTP首次暂停')
  emitMockEvent('execution:paused',{workflowId:'other',node_id:'foreign',label:'别的流程'})
  await new Promise(resolve=>setTimeout(resolve,30))
  expect(screen.queryByText('@ 别的流程')).toBeNull()
  emitMockEvent('execution:resumed',{workflowId:'other'})
  await new Promise(resolve=>setTimeout(resolve,30))
  expect(useDebugStore.getState().isPaused).toBe(true)
  if(lostResponse)server.dropNextResponse('/api/workflows/debug-http/debug/step')
  fireEvent.click(screen.getByRole('button',{name:'单步'}))
  await screen.findByText('@ 真实HTTP下一步')
  expect(stepRequests).toBe(1)
  expect((screen.getByRole('button',{name:'单步'}) as HTMLButtonElement).disabled).toBe(false)
  fireEvent.click(screen.getByRole('button',{name:'停止'}))
  await waitFor(()=>expect(mockSnapshot().run).toBeNull())
  await waitFor(()=>expect(screen.queryByRole('button',{name:'单步'})).toBeNull())
  expect(useWorkflowStore.getState().logs.at(-1)).toMatchObject({level:'info',message:'执行已停止，共执行 1 个节点，失败 0 个'})
 }finally{
  cleanup();socketService.disconnect()
  if(mockSnapshot().run)await post('/workflows/debug-http/stop',{})
  configureMock({disconnect:true});await server.close();restore()
 }
})
