import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
import type {BrowserScriptTarget} from '../lib/browserScriptContract'
describe.each(['memory','http'] as const)('browser script tests over %s',mode=>{
 let mock:typeof import('../api/mock-server');let server:Awaited<ReturnType<typeof startHttpStudioFixture>>|undefined
 let request:(path:string,body?:unknown,method?:string)=>Promise<Response>
 const prefix='/browser/script-tests'
 beforeEach(async()=>{
  const data=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value)})
  vi.resetModules();mock=await import('../api/mock-server');if(mode==='http')server=await startHttpStudioFixture(mock.mockRequest)
  request=(path,body,method)=>{const init={method:method??(body===undefined?'GET':'POST'),headers:{'Content-Type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)})};return server?fetch(`${server.origin}/api${path}`,init):mock.mockRequest(`http://autoflow-studio.mock/api${path}`,init)}
 })
 afterEach(async()=>{await request('/browser/close',{});mock.configureMock({disconnect:true});await server?.close();server=undefined;vi.unstubAllGlobals()})
 async function context():Promise<BrowserScriptTarget>{
  await request('/browser/open',{url:'https://fixture.invalid/page'})
  const value=await(await request(`${prefix}/context`)).json()
  expect(value).toMatchObject({url:'https://fixture.invalid/page',activeRequestId:null,revision:0})
  return {browserSessionId:value.browserSessionId,pageId:value.pageId,revision:value.revision}
 }
 const body=(target:BrowserScriptTarget,requestId='test')=>({requestId,context:target,code:'while(true){}',variables:{a:0,b:false}})
 it.each([undefined,null,{text:'大'.repeat(33000)}])('keeps mock result kind explicit and preserves result=%j',async value=>{
  const target=await context();mock.configureMock({scriptTest:value===undefined?{}:{result:value}})
  expect(await(await request(prefix,body(target))).json()).toMatchObject({requestId:'test',status:'running',executionKind:'mock'})
  await vi.waitFor(async()=>expect(await(await request(`${prefix}/test`)).json()).toMatchObject({status:'completed',hasResult:value!==undefined,result:value??null,executionKind:'mock'}))
 })
 it('queries and retries the original identity without creating another evaluation',async()=>{
  const target=await context();mock.configureMock({scriptTest:{hold:true}})
  await request(prefix,body(target))
  expect(await(await request(`${prefix}/context`)).json()).toMatchObject({activeRequestId:'test'})
  const reordered={variables:{b:false,a:0},code:'while(true){}',context:{revision:0,pageId:target.pageId,browserSessionId:target.browserSessionId},requestId:'test'}
  expect((await request(prefix,reordered)).status).toBe(200)
  expect((await request(prefix,{...reordered,code:'return 1'})).status).toBe(409)
  expect((await request(prefix,body(target,'second'))).status).toBe(409)
  expect(await(await request(`${prefix}/test`)).json()).toMatchObject({status:'running'})
 })
 it('cancels idempotently and releases the mutually exclusive browser slot',async()=>{
  const target=await context();mock.configureMock({scriptTest:{hold:true}});await request(prefix,body(target))
  await request('/workflows',{id:'other',nodes:[{id:'page',type:'open_page'}]})
  for(const path of ['/workflows/other/execute','/recorder/start','/element-picker/start'])expect((await request(path,path.endsWith('/start')?{sessionId:'blocked-session'}:{})).status).toBe(409)
  for(let i=0;i<2;i++)expect(await(await request(`${prefix}/test/cancel`,{})).json()).toMatchObject({status:'cancelled'})
  expect(await(await request(`${prefix}/context`)).json()).toMatchObject({activeRequestId:null})
  expect((await request(prefix,body(target,'next'))).status).toBe(200)
 })
 it('expires in-flight tests on navigation and rejects their old page revision',async()=>{
  const target=await context();mock.configureMock({scriptTest:{hold:true}});await request(prefix,body(target))
  await request('/browser/navigate',{url:'https://fixture.invalid/next'})
  expect(await(await request(`${prefix}/test`)).json()).toMatchObject({status:'expired',error:expect.stringContaining('失效')})
  expect((await request(prefix,body(target,'next'))).status).toBe(409)
  const current=await(await request(`${prefix}/context`)).json();expect(current.revision).toBe(1)
  await request('/browser/close',{});expect((await request(`${prefix}/context`)).status).toBe(409)
  const reopened=await context();expect(reopened.browserSessionId).not.toBe(target.browserSessionId)
 })
 it('retains an explicit service failure and never replaces it with a successful mock result',async()=>{
  const target=await context();mock.configureMock({scriptTest:{error:'模拟页面求值失败'}});await request(prefix,body(target))
  await vi.waitFor(async()=>expect(await(await request(`${prefix}/test`)).json()).toMatchObject({status:'failed',error:'模拟页面求值失败',hasResult:false,result:null}))
  expect(await(await request(`${prefix}/test/cancel`,{})).json()).toMatchObject({status:'failed'})
 })
 it('rejects missing context, invalid payloads, oversized UTF8 and unsupported methods',async()=>{
  expect((await request(`${prefix}/context`)).status).toBe(409)
  const target=await context()
  for(const patch of [{code:' '},{variables:[]},{context:{...target,revision:-1}},{code:'中'.repeat(400000)}])expect((await request(prefix,{...body(target),...patch})).status).toBe(422)
  expect((await request(`${prefix}/unknown`)).status).toBe(404)
  expect((await request(prefix)).status).toBe(405)
  expect((await request(`${prefix}/context`,{})).status).toBe(405)
 })
})
