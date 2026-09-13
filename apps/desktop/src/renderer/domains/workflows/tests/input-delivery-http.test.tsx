import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {InputPromptDialog} from '../components/InputPromptDialog'
import {socketService} from '../events'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'

afterEach(()=>{cleanup();socketService.disconnect();vi.unstubAllGlobals()})
it.each([false,true])('keeps a recoverable input submission over real HTTP with queryInitiallyOffline=%s',async queryInitiallyOffline=>{
 vi.resetModules()
 const {mockRequest,configureMock,mockSnapshot}=await import('../api/mock-server')
 const storage=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>storage.get(key)??null,setItem:(key:string,value:string)=>storage.set(key,value)})
 let unavailable=queryInitiallyOffline
 const postedIds:string[]=[];const queriedIds:string[]=[]
 const server=await startHttpStudioFixture(async(input,init)=>{
  const request=input as Request
  if(request.method==='POST' && request.url.endsWith('/events/commands')){
   const command=await request.clone().json()
   if(command.event==='input_prompt_result')postedIds.push(command.commandId)
  }
  if(request.method==='GET' && request.url.includes('/events/commands/')){
   queriedIds.push(request.url.split('/').at(-1)!)
   if(unavailable)return Response.json({error:'查询暂不可用'},{status:503})
  }
  return mockRequest(input,init)
 })
 socketService.disconnect();const restore=configureStudioConnection(server.origin,fetch)
 const post=(path:string,body:unknown)=>fetch(`${server.origin}/api${path}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
 try{
  render(<InputPromptDialog />);socketService.connect()
  await waitFor(()=>expect(socketService.isConnected()).toBe(true))
  await post('/workflows',{id:'delivery-http',name:'HTTP输入验收',nodes:[{id:'input',type:'input_prompt',data:{variableName:'answer',inputMode:'single',promptTitle:'HTTP输入验收',defaultValue:'before'}}],variables:[]})
  await post('/workflows/delivery-http/execute',{})
  const input=await screen.findByDisplayValue('before')
  fireEvent.change(input,{target:{value:'用户草稿'}})
  server.dropNextResponse('/api/events/commands')
  fireEvent.click(screen.getByRole('button',{name:'确定'}))
  if(queryInitiallyOffline){
   await screen.findByRole('button',{name:'查询提交结果'})
   expect(screen.queryByDisplayValue('用户草稿')).not.toBeNull()
   expect(postedIds).toHaveLength(1)
   unavailable=false
   await act(async()=>fireEvent.click(screen.getByRole('button',{name:'查询提交结果'})))
  }
  await waitFor(()=>expect(screen.queryByRole('dialog')).toBeNull())
  expect(postedIds).toHaveLength(1)
  expect(queriedIds.length).toBe(queryInitiallyOffline?2:1)
  expect(queriedIds.every(id=>id===postedIds[0])).toBe(true)
  expect((await(await fetch(`${server.origin}/api/workflows/global-variables`)).json()).variables.answer).toBe('用户草稿')
 }finally{
  cleanup();socketService.disconnect()
  if(mockSnapshot().run)await post('/workflows/delivery-http/stop',{})
  configureMock({disconnect:true});await server.close();restore()
 }
})

it.each(['pending','answered','cancelled','expired'] as const)('replays the HTTP journal safely when the input is %s',async status=>{
 vi.resetModules()
 const {mockRequest,configureMock,mockSnapshot}=await import('../api/mock-server')
 const storage=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>storage.get(key)??null,setItem:(key:string,value:string)=>storage.set(key,value)})
 const server=await startHttpStudioFixture(mockRequest)
 socketService.disconnect();const restore=configureStudioConnection(server.origin,fetch)
 const post=(path:string,body:unknown)=>fetch(`${server.origin}/api${path}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
 try{
  await post('/workflows',{id:'recovery-input',name:'恢复验收',nodes:[{id:'input',type:'input_prompt',data:{variableName:'answer',inputMode:'single',promptTitle:'恢复验收',defaultValue:'恢复输入'}}],variables:[]})
  render(<InputPromptDialog />);socketService.connect()
  await post('/workflows/recovery-input/execute',{})
  await screen.findByDisplayValue('恢复输入')
  if(status==='answered'||status==='cancelled'){
   fireEvent.click(screen.getByRole('button',{name:status==='answered'?'确定':'取消'}))
   await waitFor(()=>expect(screen.queryByRole('dialog')).toBeNull())
  }else if(status==='expired'){
   await post('/workflows/recovery-input/stop',{})
   await waitFor(()=>expect(screen.queryByRole('dialog')).toBeNull())
  }
  cleanup();socketService.disconnect();render(<InputPromptDialog />);socketService.connect()
  await waitFor(()=>expect(socketService.isConnected()).toBe(true))
  if(status==='pending') await screen.findByDisplayValue('恢复输入')
  else { await new Promise(resolve=>setTimeout(resolve,250));expect(screen.queryByRole('dialog')).toBeNull() }
 }finally{
  cleanup();socketService.disconnect()
  if(mockSnapshot().run)await post('/workflows/recovery-input/stop',{})
  configureMock({disconnect:true});await server.close();restore()
 }
})

it('retries a failed state read and ignores a late lookup for an older prompt',async()=>{
 vi.resetModules()
 const {mockRequest,configureMock,emitMockEvent}=await import('../api/mock-server')
 let oldReply!:(value:Response)=>void
 let oldRead=false;let newReads=0
 const state=(id:string)=>({requestId:id,workflowId:'lookup-run',nodeId:id,status:'pending'})
 const server=await startHttpStudioFixture(async(input,init)=>{
  const request=input as Request
  if(request.url.endsWith('/input-prompts/old')){oldRead=true;return new Promise<Response>(resolve=>{oldReply=resolve})}
  if(request.url.endsWith('/input-prompts/new')){
   newReads++
   return newReads===1?Response.json({error:'临时断线'},{status:503}):Response.json(state('new'))
  }
  return mockRequest(input,init)
 })
 socketService.disconnect();const restore=configureStudioConnection(server.origin,fetch)
 try{
  render(<InputPromptDialog />);socketService.connect()
  await waitFor(()=>expect(socketService.isConnected()).toBe(true))
  const prompt=(id:string)=>({requestId:id,workflowId:'lookup-run',nodeId:id,variableName:'answer',title:'迟到保护',message:'输入',inputMode:'single',defaultValue:id})
  emitMockEvent('execution:input_prompt',prompt('old'))
  await waitFor(()=>expect(oldRead).toBe(true))
  emitMockEvent('execution:input_prompt',prompt('new'))
  await screen.findByDisplayValue('new',{}, {timeout:2500})
  await act(async()=>oldReply(Response.json(state('old'))))
  expect(screen.queryByDisplayValue('old')).toBeNull()
  expect(screen.queryByDisplayValue('new')).not.toBeNull()
  expect(newReads).toBe(2)
  emitMockEvent('execution:completed',{workflowId:'another-run',result:{status:'stopped',executedNodes:0,failedNodes:0}})
  await new Promise(resolve=>setTimeout(resolve,50))
  expect(screen.queryByDisplayValue('new')).not.toBeNull()
  emitMockEvent('execution:completed',{workflowId:'lookup-run',result:{status:'stopped',executedNodes:0,failedNodes:0}})
  await waitFor(()=>expect(screen.queryByRole('dialog')).toBeNull())
 }finally{cleanup();socketService.disconnect();configureMock({disconnect:true});oldReply?.(Response.json(state('old')));await server.close();restore()}
})
