import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {elementPickerApi} from '../api'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'

describe.each(['memory','http'] as const)('picker identity over %s',mode=>{
 let mock:typeof import('../api/mock-server')
 let server:Awaited<ReturnType<typeof startHttpStudioFixture>>|null
 let restore:()=>void
 let request:(path:string,body?:unknown)=>Promise<Response>
 beforeEach(async()=>{
  vi.resetModules();mock=await import('../api/mock-server')
  server=mode==='http'?await startHttpStudioFixture(mock.mockRequest):null
  restore=configureStudioConnection(server?.origin??'http://autoflow-studio.mock',server?fetch:mock.mockRequest)
  request=(path,body)=>{
   const init=body===undefined?{}:{method:'POST',body:JSON.stringify(body),headers:{'Content-Type':'application/json'}}
   return server?fetch(`${server.origin}/api${path}`,init):mock.mockRequest(`http://autoflow-studio.mock/api${path}`,init)
  }
 })
 afterEach(async()=>{mock.configureMock({offline:false});await request('/browser/close',{});await server?.close();restore()})
 it('reuses a stable startup identity and preserves an already selected result',async()=>{
  const first=await elementPickerApi.start('https://example.test',{locale:'zh-CN'})
  expect(first.success).toBe(true)
  const sessionId=first.data!.sessionId
  mock.selectMockElement('#first')
  expect(await elementPickerApi.start('https://example.test',{locale:'zh-CN'})).toMatchObject({success:true,data:{sessionId,selected:true}})
  expect(await elementPickerApi.getSelected()).toMatchObject({success:true,data:{sessionId,selector:'#first'}})
  expect((await request('/element-picker/start',{sessionId,url:'https://different.test'})).status).toBe(409)
  expect((await request('/element-picker/start',{sessionId:'another'})).status).toBe(409)
  expect(mock.mockSnapshot()).toMatchObject({picking:true,pickerSessionId:sessionId})
 })
 it('rejects unbound reads, stops and tests without changing the active selection',async()=>{
  await elementPickerApi.start();mock.selectMockElement('#private-result')
  for(const path of ['/selected','/result','/similar']){
   expect((await request(`/element-picker${path}`)).status).toBe(409)
   expect((await request(`/element-picker${path}?sessionId=other`)).status).toBe(409)
  }
  expect((await request('/element-picker/stop',{sessionId:'other'})).status).toBe(409)
  expect((await request('/element-picker/test-selector',{sessionId:'other',selector:'#target'})).status).toBe(409)
  expect(await elementPickerApi.getSelected()).toMatchObject({success:true,data:{selector:'#private-result'}})
 })
 it('retains ownership after failed cleanup and prevents an old session from controlling its replacement',async()=>{
  const first=(await elementPickerApi.start()).data!.sessionId
  mock.configureMock({failNextPickerStop:true})
  expect(await elementPickerApi.stop()).toMatchObject({success:false,httpStatus:503})
  expect(mock.mockSnapshot()).toMatchObject({picking:true,pickerSessionId:first})
  expect(await elementPickerApi.stop()).toMatchObject({success:true,data:{sessionId:first,active:false}})
  expect((await request('/element-picker/stop',{sessionId:first})).status).toBe(200)
  expect((await request('/element-picker/start',{sessionId:first})).status).toBe(409)
  const second=(await elementPickerApi.start()).data!.sessionId
  expect(second).not.toBe(first)
  mock.selectMockElement('#second')
  expect((await request(`/element-picker/selected?sessionId=${first}`)).status).toBe(409)
  expect((await request('/element-picker/stop',{sessionId:first})).status).toBe(409)
  expect(await elementPickerApi.getSelected()).toMatchObject({success:true,data:{sessionId:second,selector:'#second'}})
 })
 it('adopts the current session after renderer reconnection and can close it',async()=>{
  expect((await request('/element-picker/start',{sessionId:'existing'})).status).toBe(200)
  expect(await elementPickerApi.getStatus()).toMatchObject({success:true,data:{sessionId:'existing',active:true}})
  mock.selectMockSimilarElements()
  expect(await elementPickerApi.getSimilar()).toMatchObject({success:true,data:{selected:true}})
  expect(await elementPickerApi.stop()).toMatchObject({success:true,data:{sessionId:'existing',active:false}})
 })
 it('can close a recovered session without first opening the picker panel',async()=>{
  await request('/element-picker/start',{sessionId:'existing'})
  expect(await elementPickerApi.stop()).toMatchObject({success:true,data:{sessionId:'existing',active:false}})
  expect(mock.mockSnapshot().picking).toBe(false)
 })
 it.each([{}, {sessionId:''}, {sessionId:' '}, {sessionId:3}, {sessionId:'picker',url:false}, {sessionId:'picker',browserConfig:[]}, {sessionId:'picker',extra:1}])('rejects a missing identity or invalid startup configuration %j',async body=>{
  expect((await request('/element-picker/start',body)).status).toBe(422)
  expect(mock.mockSnapshot().picking).toBe(false)
 })
})

it.each(['start','stop'] as const)('queries the original session after an HTTP %s response is lost',async action=>{
 vi.resetModules();const mock=await import('../api/mock-server')
 const paths:string[]=[]
 const server=await startHttpStudioFixture(async(input,init)=>{paths.push(new URL(input instanceof Request?input.url:String(input)).pathname);return mock.mockRequest(input,init)})
 const restore=configureStudioConnection(server.origin,fetch)
 try{
  if(action==='stop')await elementPickerApi.start()
  paths.length=0;server.dropNextResponse(`/api/element-picker/${action}`)
  const result=await elementPickerApi[action]()
  expect(result).toMatchObject({success:true,data:{active:action==='start'}})
  expect(paths.filter(path=>path===`/api/element-picker/${action}`)).toHaveLength(1)
  expect(paths).toContain('/api/element-picker/status')
  expect(mock.mockSnapshot().picking).toBe(action==='start')
 }finally{await elementPickerApi.stop();await server.close();restore()}
})

it('rejects a selected result that arrives after another picker session has started',async()=>{
 vi.resetModules();const mock=await import('../api/mock-server')
 let release!:()=>void
 const gate=new Promise<void>(resolve=>{release=resolve})
 const restore=configureStudioConnection('http://autoflow-studio.mock',async(input,init)=>{
  const result=await mock.mockRequest(input,init)
  if(String(input).includes('/element-picker/selected?'))await gate
  return result
 })
 try{
  await elementPickerApi.start();mock.selectMockElement('#old')
  const pending=elementPickerApi.getSelected()
  await elementPickerApi.stop();await elementPickerApi.start();mock.selectMockElement('#new')
  release()
  expect(await pending).toMatchObject({success:false,error:expect.stringContaining('过期')})
 }finally{release();await elementPickerApi.stop();restore()}
})

it('keeps the same startup identity when both acknowledgement and recovery query are unavailable',async()=>{
 vi.resetModules();const mock=await import('../api/mock-server')
 let unavailable=true
 const starts:string[]=[]
 const restore=configureStudioConnection('http://autoflow-studio.mock',async(input,init)=>{
  if(String(input).endsWith('/start')){
   starts.push(JSON.parse(String(init?.body)).sessionId)
   const result=await mock.mockRequest(input,init)
   if(unavailable)throw new TypeError('Failed to fetch')
   return result
  }
  if(unavailable)throw new TypeError('Failed to fetch')
  return mock.mockRequest(input,init)
 })
 try{
  expect(await elementPickerApi.start()).toMatchObject({success:false,outcomeUnknown:true})
  expect(mock.mockSnapshot().picking).toBe(true)
  unavailable=false
  expect(await elementPickerApi.start()).toMatchObject({success:true,data:{sessionId:starts[0]}})
  expect(starts).toHaveLength(2);expect(starts[1]).toBe(starts[0])
 }finally{unavailable=false;await elementPickerApi.stop();restore()}
})

it('releases an unaccepted startup identity after a definite status rejection',async()=>{
 const ids:string[]=[]
 const restore=configureStudioConnection('http://picker-unaccepted.test',async(input,init)=>{
  if(String(input).endsWith('/start')){ids.push(JSON.parse(String(init?.body)).sessionId);throw new TypeError('Failed to fetch')}
  return Response.json({success:false,error:'会话不存在'},{status:409})
 })
 try{
  expect(await elementPickerApi.start()).toMatchObject({success:false,httpStatus:409})
  expect(await elementPickerApi.start()).toMatchObject({success:false,httpStatus:409})
  expect(ids).toHaveLength(2);expect(ids[1]).not.toBe(ids[0])
 }finally{restore()}
})

it.each(['start','status','selected','test-selector'] as const)('discards a late %s response from another connection',async action=>{
 vi.resetModules();const mock=await import('../api/mock-server')
 let hold=false,release!:()=>void
 const gate=new Promise<void>(resolve=>{release=resolve})
 const restore=configureStudioConnection('http://autoflow-studio.mock',async(input,init)=>{
  const result=await mock.mockRequest(input,init)
  if(hold&&String(input).includes(`/element-picker/${action}`))await gate
  return result
 })
 let restoreNew:(()=>void)|undefined
 try{
  if(action!=='start')await elementPickerApi.start()
  hold=true
  const pending=action==='start'?elementPickerApi.start():action==='status'?elementPickerApi.getStatus():action==='selected'?elementPickerApi.getSelected():elementPickerApi.testSelector('#target')
  const newRequests=vi.fn(async()=>Response.json({success:true,sessionId:'new',active:true,selected:false}))
  restoreNew=configureStudioConnection('http://new-picker.test',newRequests)
  release()
  expect(await pending).toMatchObject({success:false})
  expect(newRequests).not.toHaveBeenCalled()
  expect(await elementPickerApi.getStatus()).toMatchObject({success:true,data:{sessionId:'new'}})
 }finally{release();restoreNew?.();await mock.mockRequest('http://autoflow-studio.mock/api/browser/close',{method:'POST'});restore()}
})

it.each([{selected:'true'}, {selected:true}, {selected:true,element:{selector:''}}, {selected:true,element:{selector:42}}])('rejects a malformed selected element %j',async patch=>{
 const restore=configureStudioConnection('http://invalid-picker.test',async input=>Response.json(String(input).includes('/status')
  ?{success:true,sessionId:'picker',active:true,selected:false}
  :{success:true,sessionId:'picker',active:true,...patch}))
 try{expect(await elementPickerApi.getSelected()).toMatchObject({success:false,error:'拾取结果格式错误，未应用定位信息'})}finally{restore()}
})
