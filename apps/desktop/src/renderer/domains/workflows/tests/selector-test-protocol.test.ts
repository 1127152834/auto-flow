import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {elementPickerApi} from '../api'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
describe.each(['memory','http'] as const)('selector protocol over %s',mode=>{
 let mock:typeof import('../api/mock-server')
 let server:Awaited<ReturnType<typeof startHttpStudioFixture>>|null
 let restore:()=>void
 let request:(path:string,body?:unknown,method?:string)=>Promise<Response>
 beforeEach(async()=>{
  vi.resetModules();mock=await import('../api/mock-server')
  server=mode==='http'?await startHttpStudioFixture(mock.mockRequest):null
  restore=configureStudioConnection(server?.origin??'http://autoflow-studio.mock',server?fetch:mock.mockRequest)
  request=(path,body,method=body===undefined?'GET':'POST')=>{const init={method,...(body===undefined?{}:{body:JSON.stringify(body),headers:{'Content-Type':'application/json'}})};return server?fetch(`${server.origin}/api${path}`,init):mock.mockRequest(`http://autoflow-studio.mock/api${path}`,init)}
 })
 afterEach(async()=>{mock.configureMock({disconnect:true});await server?.close();restore()})
 it('reports a closed browser instead of fabricated matches',async()=>{
  expect(await elementPickerApi.testSelector('#target')).toMatchObject({success:false,error:expect.stringContaining('浏览器未打开')})
 })
 it.each([['none',0],['single',1],['multiple',4]] as const)('returns the explicit %s fixture as %i matches',async(scenario,count)=>{
  await request('/browser/open',{})
  mock.configureMock({selectorTest:scenario})
  expect(await elementPickerApi.testSelector('#target')).toMatchObject({success:true,data:{success:true,matched:count>0,count}})
 })
 it('returns explicit locator errors rather than treating them as zero matches',async()=>{
  await request('/browser/open',{});mock.configureMock({selectorTest:'error'})
  expect(await elementPickerApi.testSelector('#target')).toMatchObject({success:false,error:expect.stringContaining('Mock 定位失败')})
 })
 it.each([{selector:12},{selector:'#target',highlight:'true'},{selector:'#target',hints:[]},{selector:''}])('rejects malformed request %j',async payload=>{
  await request('/browser/open',{})
  expect((await request('/element-picker/test-selector',payload)).status).toBe(422)
 })
 it('rejects the wrong HTTP method',async()=>{
  expect((await request('/element-picker/test-selector')).status).toBe(405)
 })
})
it.each([
 {success:true,matched:true,count:-1},
 {success:true,matched:true,count:1.5},
 {success:true,matched:true,count:'1'},
 {success:true,matched:true,count:0},
 {success:true,matched:false,count:1},
 {success:true,matched:true},
 {success:true,matched:true,count:1,element:{text:123}},
 {success:true,matched:true,count:1,tried:'invalid'},
])('rejects a malformed selector result %j',async result=>{
 const restore=configureStudioConnection('http://selector-response.test',async()=>Response.json(result))
 try{expect(await elementPickerApi.testSelector('#target')).toMatchObject({success:false,error:expect.stringContaining('定位测试响应格式错误')})}finally{restore()}
})
