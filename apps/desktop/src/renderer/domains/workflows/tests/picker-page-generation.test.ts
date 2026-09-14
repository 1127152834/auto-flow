import {expect,it,vi} from 'vitest'
import {browserApi,elementPickerApi} from '../api'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'

// A completed old-page response is held in transit while navigation is confirmed.
// This tests frontend response ownership, not iframe discovery or browser execution.
it.each(['memory','http'] as const)('PICKER.page-generation.%s: rejects a selected element produced before confirmed navigation',async mode=>{
 await checkLateResult(mode,'selected')
})
it.each(['memory','http'] as const)('SELECTOR.page-generation.%s: rejects a locator result produced before confirmed navigation',async mode=>{
 await checkLateResult(mode,'test-selector')
})
it.each(['memory','http'] as const)('SELECTOR.page-poll.%s: rejects an old result after polling observes another page revision and accepts a fresh request',async mode=>{
 await checkLateResult(mode,'test-selector','poll')
})
async function checkLateResult(mode:'memory'|'http',action:'selected'|'test-selector',observation:'command'|'poll'='command'){
 vi.resetModules()
 const mock=await import('../api/mock-server')
 let release!:()=>void
 const gate=new Promise<void>(resolve=>{release=resolve})
 let reached!:()=>void
 const pendingResponse=new Promise<void>(resolve=>{reached=resolve})
 let hold=false
 const transport=async(input:RequestInfo|URL,init?:RequestInit)=>{
  const response=await mock.mockRequest(input,init)
  if(hold&&(input instanceof Request?input.url:String(input)).includes(`/element-picker/${action}`)){reached();await gate}
  return response
 }
 const server=mode==='http'?await startHttpStudioFixture(transport):null
 const restore=configureStudioConnection(server?.origin??'http://autoflow-studio.mock',server?fetch:transport)
 try{
  expect((await browserApi.open()).success).toBe(true)
  mock.configureMockBrowserPages([{pageId:'page',url:'https://fixture.invalid/before',title:'原文档'}],'page')
  expect((await elementPickerApi.start()).success).toBe(true)
  if(action==='selected')mock.selectMockElement('#old-document-element')
  const before=(await browserApi.pages()).data!
  hold=true
  const result=action==='selected'?elementPickerApi.getSelected():elementPickerApi.testSelector('#old-document-element',{tag:'button'})
  await pendingResponse
  if(observation==='poll')mock.configureMockBrowserPages([{pageId:'page',url:'https://fixture.invalid/after',title:'新文档'}],'page')
  const navigated=observation==='poll'?await browserApi.pages():await browserApi.page({sessionId:before.sessionId,expectedRevision:before.revision,pageId:'page',action:'navigate',url:'https://fixture.invalid/after'})
  expect(navigated.success).toBe(true)
  expect(navigated.data!.revision).toBeGreaterThan(before.revision)
  release()
  // The source page is no longer current even though the service connection is unchanged.
  expect(await result).toMatchObject({success:false})
  hold=false
  expect(await elementPickerApi.getStatus()).toMatchObject({success:true,data:{active:false}})
  expect((await elementPickerApi.start()).success).toBe(true)
  if(action==='selected'){
   mock.selectMockElement('#new-document-element')
   expect(await elementPickerApi.getSelected()).toMatchObject({success:true,data:{selected:true,element:{selector:'#new-document-element'}}})
  }else expect(await elementPickerApi.testSelector('#new-document-element')).toMatchObject({success:true,data:{matched:true,count:1}})
 }finally{
  release();hold=false
  await browserApi.close();mock.configureMock({disconnect:true});await server?.close();restore()
 }
}
