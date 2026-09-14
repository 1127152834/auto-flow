import {expect,it,vi} from 'vitest'
import {browserApi,currentBrowserSession,elementPickerApi} from '../api'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
it.each(['memory','http'] as const)('reports confirmed browser and picker flags over %s',async mode=>{
 vi.resetModules();const mock=await import('../api/mock-server');const server=mode==='http'?await startHttpStudioFixture(mock.mockRequest):null;const restore=configureStudioConnection(server?.origin??'http://autoflow-studio.mock',server?fetch:mock.mockRequest)
 try{
  expect(await browserApi.getStatus()).toMatchObject({success:true,data:{isOpen:false,pickerActive:false}})
  await browserApi.open();expect(await browserApi.getStatus()).toMatchObject({success:true,data:{isOpen:true,pickerActive:false}})
  await elementPickerApi.start();expect(await browserApi.getStatus()).toMatchObject({success:true,data:{isOpen:true,pickerActive:true}})
  await elementPickerApi.stop();await browserApi.close();expect(await browserApi.getStatus()).toMatchObject({success:true,data:{isOpen:false,pickerActive:false}})
 }finally{mock.configureMock({disconnect:true});await server?.close();restore()}
})
it.each([{},null,[],{isOpen:true},{isOpen:'false',pickerActive:false},{isOpen:false,pickerActive:1}])('rejects invalid browser status %j',async value=>{
 const restore=configureStudioConnection('http://status-invalid.test',async()=>Response.json(value))
 try{expect(await browserApi.getStatus()).toMatchObject({success:false,error:'浏览器状态响应格式错误，保留最后确认状态'})}finally{restore()}
})
it.each(['status','pages'] as const)('does not resurrect occupancy from a late %s response after confirmed closure',async kind=>{
 let delay=false
 let finish!:(response:Response)=>void
 const restore=configureStudioConnection('http://browser-late.test',async input=>{
  const path=new URL(String(input)).pathname
  if(path.endsWith('/close'))return Response.json({success:true})
  if(delay)return new Promise<Response>(resolve=>{finish=resolve})
  return Response.json({isOpen:true,pickerActive:false,sessionId:'browser-original'})
 })
 try{
  await browserApi.getStatus();delay=true
  const pending=kind==='status'?browserApi.getStatus():browserApi.pages()
  expect((await browserApi.close()).success).toBe(true)
  finish(Response.json(kind==='status'?{isOpen:true,pickerActive:false,sessionId:'browser-original'}:{sessionId:'browser-original',revision:1,targetPageId:'page',pages:[{pageId:'page',url:'about:blank',title:'旧页面'}]}))
  expect((await pending).success).toBe(false)
  expect(currentBrowserSession()).toBeNull()
 }finally{restore()}
})
it('does not release browser startup while a concurrent status still reports closed',async()=>{
 let finish!:(response:Response)=>void
 let opened=false
 let closes=0
 const restore=configureStudioConnection('http://browser-starting.test',async input=>{
  const path=new URL(String(input)).pathname
  if(path.endsWith('/open'))return new Promise<Response>(resolve=>{finish=resolve})
  if(path.endsWith('/close')){closes++;opened=false;return Response.json({success:true})}
  return Response.json({isOpen:opened,pickerActive:false,sessionId:opened?'confirmed-start':''})
 })
 try{
  const pending=browserApi.open()
  await browserApi.getStatus()
  expect(currentBrowserSession()).toBeTruthy()
  expect((await browserApi.close()).success).toBe(false)
  expect(closes).toBe(0)
  opened=true;finish(Response.json({success:true}));await pending
  expect((await browserApi.close()).success).toBe(true)
  expect(closes).toBe(1)
 }finally{restore()}
})
