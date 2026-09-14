import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
vi.hoisted(()=>{const data=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value),removeItem:(key:string)=>data.delete(key)})})
import {startHttpStudioFixture} from './fixtures/http-studio-server'
describe.each(['memory','http'] as const)('startup admission over %s',mode=>{
 let Toolbar:typeof import('../components/Toolbar')['Toolbar']
 let store:typeof import('../editor-store')['useWorkflowStore']
 let socketService:typeof import('../events')['socketService']
 let mock:typeof import('../api/mock-server')
 let server:Awaited<ReturnType<typeof startHttpStudioFixture>>|undefined
 let restore:()=>void
 let queryUnavailable=false
 let lost:boolean
 let starts:number
 let request:(path:string,body?:unknown)=>Promise<Response>
 beforeEach(async()=>{
  vi.resetModules();lost=false;starts=0;queryUnavailable=false
  const data=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value),removeItem:(key:string)=>data.delete(key)})
  const {configureStudioConnection}=await import('../api/config')
  const {useDebugStore}=await import('../hooks/stores/debugStore')
  ;({Toolbar}=await import('../components/Toolbar'))
  ;({useWorkflowStore:store}=await import('../editor-store'))
  ;({socketService}=await import('../events'))
  mock=await import('../api/mock-server');if(mode==='http')server=await startHttpStudioFixture(mock.mockRequest)
  const origin=server?.origin??'http://autoflow-studio.mock'
  restore=configureStudioConnection(origin,async(input,init)=>{
   if(queryUnavailable&&/\/workflow-runs\/[^/]+$/.test(String(input)))return Response.json({error:'终态查询暂不可用'},{status:503})
   const isStart=/\/workflows\/[^/]+\/execute$/.test(String(input));if(isStart)starts++
   const response=await(server?fetch(input,init):mock.mockRequest(input,init))
   if(isStart && lost){lost=false;throw new TypeError('响应在启动接受后丢失')}
   return response
  })
  request=(path,body)=>{const init=body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)};return server?fetch(`${origin}/api${path}`,init):mock.mockRequest(`${origin}/api${path}`,init)}
  store.getState().clearWorkflow();store.getState().addNode('open_page',{x:0,y:0});useDebugStore.setState({breakpoints:new Set(),stepMode:false})
 })
 afterEach(async()=>{cleanup();if(mock.mockSnapshot().run)await request(`/workflows/${mock.mockSnapshot().run}/stop`,{});socketService.disconnect();mock.configureMock({disconnect:true});await server?.close();server=undefined;restore();vi.unstubAllGlobals()})
 it.each([false,true])('keeps a single accepted request before stream recovery, lost=%s',async lose=>{
  lost=lose;render(<Toolbar/>);fireEvent.keyDown(window,{key:'F5'})
  await waitFor(()=>expect(screen.getByRole('status').textContent).toContain('等待启动确认'))
  await waitFor(()=>expect(store.getState().logs.some(log=>log.message.includes(lose?'启动状态尚未确认':'启动请求已接受'))).toBe(true))
  await act(async()=>{fireEvent.keyDown(window,{key:'F5'});window.dispatchEvent(new CustomEvent('run-from-node',{detail:{nodeId:store.getState().nodes[0].id}}))})
  expect(starts).toBe(1)
  await waitFor(()=>expect(mock.mockSnapshot().run).toBeNull())
  act(()=>socketService.connect())
  await waitFor(()=>expect(store.getState().executionStatus).toBe('completed'),{timeout:2500})
  expect(screen.queryByText('等待启动确认')).toBeNull();expect(starts).toBe(1)
 })
 it.each([true,false])('requires confirmed terminal state from query or recovered event, queryUnavailable=%s',async unavailable=>{
  queryUnavailable=unavailable
  render(<Toolbar/>);fireEvent.keyDown(window,{key:'F5'})
  await waitFor(()=>expect(store.getState().logs.some(log=>log.message.includes('启动请求已接受'))).toBe(true))
  fireEvent.click(screen.getByRole('button',{name:'停止启动请求'}))
  await waitFor(()=>expect(mock.mockSnapshot().run).toBeNull())
  if(unavailable)expect(screen.getByRole('status').textContent).toContain('等待启动确认')
  else await waitFor(()=>expect(store.getState().executionStatus).toBe('stopped'))
  act(()=>socketService.connect())
  await waitFor(()=>expect(store.getState().executionStatus).toBe('stopped'),{timeout:2500})
  expect(screen.queryByText('等待启动确认')).toBeNull();expect(starts).toBe(1)
 })
})
