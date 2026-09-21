import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {DebugBar} from '../components/DebugBar'
import {socketService} from '../events'
import {useWorkflowStore} from '../editor-store'
import {useDebugStore} from '../hooks/stores/debugStore'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
afterEach(()=>{cleanup();socketService.disconnect();useDebugStore.getState().clearPaused();vi.unstubAllGlobals()})
it('consumes a failure-pause event as a read-only inspection state',async()=>{
 vi.resetModules()
 const mock=await import('../api/mock-server')
 const restore=configureStudioConnection('http://autoflow-studio.mock',mock.mockRequest)
 try{
  render(<DebugBar/>);socketService.connect();await waitFor(()=>expect(socketService.isConnected()).toBe(true))
  mock.emitMockEvent('execution:started',{workflowId:'failed-http',runId:'failed-run'})
  mock.emitMockEvent('execution:failed_paused',{workflowId:'failed-http',runId:'failed-run',pauseId:'failed-pause',controlRevision:2,node_id:'failed-node',label:'真实失败节点',variables:{count:1},error:'定位失败'})
  await screen.findByText('失败暂停')
  expect(screen.getByText('@ 真实失败节点')).toBeTruthy()
  expect(screen.getByRole('alert').textContent).toContain('定位失败')
  expect(useDebugStore.getState().pausedReason).toBe('failure')
 }finally{restore();mock.configureMock({disconnect:true})}
})
it.each([false,true])('controls a real HTTP fixture and rejects foreign pause events; lostResponse=%s',async lostResponse=>{
 vi.resetModules()
 const {mockRequest,configureMock,mockSnapshot,emitMockEvent}=await import('../api/mock-server')
 const storage=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>storage.get(key)??null,setItem:(key:string,value:string)=>storage.set(key,value)})
 let stepRequests=0,commandQueries=0
 let stepBody:unknown
 const server=await startHttpStudioFixture(async(input,init)=>{
  const request=input as Request
  if(request.url.endsWith('/debug/step')){stepRequests++;stepBody=await request.clone().json()}
  if(request.method==='GET' && request.url.includes('/events/commands/'))commandQueries++
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
  const pause=useDebugStore.getState().pauseContext
  if(lostResponse)server.dropNextResponse('/api/workflows/debug-http/debug/step')
  fireEvent.click(screen.getByRole('button',{name:'单步'}))
  await screen.findByText('@ 真实HTTP下一步')
  emitMockEvent('execution:resumed',{workflowId:'debug-http',pauseId:pause?.pauseId})
  await new Promise(resolve=>setTimeout(resolve,30))
  expect(useDebugStore.getState().isPaused).toBe(true)
  expect(useDebugStore.getState().pauseContext?.pauseId).not.toBe(pause?.pauseId)
  expect(stepRequests).toBe(1)
  expect(stepBody).toMatchObject({...pause,commandId:expect.any(String)})
  if(lostResponse)await waitFor(()=>expect(commandQueries).toBe(1))
  else expect(commandQueries).toBe(0)
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
