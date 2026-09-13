import {afterEach,expect,it,vi} from 'vitest'
import {StudioEventClient} from '../api/event-client'
import {setStudioTransport} from '../api/transport'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
afterEach(()=>vi.unstubAllGlobals())
for(const mode of ['memory','http'] as const){
 it.each([500,502,503])(`queries the original command after an applied command returns HTTP %s over ${mode}`,async status=>{
  vi.resetModules();const {mockRequest,configureMock}=await import('../api/mock-server')
  let posts=0;let lookups=0
  const handler:typeof mockRequest=async(input,init)=>{
   const url=input instanceof Request?input.url:String(input)
   if(url.endsWith('/events/commands')){
    posts++;await mockRequest(input,init)
    return Response.json({error:'提交结果经过网关时失败'},{status})
   }
   if(url.includes('/events/commands/'))lookups++
   return mockRequest(input,init)
  }
  const server=mode==='http'?await startHttpStudioFixture(handler):null
  const restore=setStudioTransport(server?fetch:handler)
  const client=new StudioEventClient(server?.origin??'http://autoflow-studio.mock')
  try{
   const commandId=`applied-${mode}-${status}`
   expect(await client.command('set_verbose_log',{enabled:true},commandId)).toMatchObject({commandId,success:true,httpStatus:200})
   expect(posts).toBe(1);expect(lookups).toBe(1)
  }finally{client.disconnect();configureMock({disconnect:true});await server?.close();restore()}
 })
 it.each([500,502,503])(`keeps HTTP %s unconfirmed when no command record can be found over ${mode}`,async status=>{
  vi.resetModules();const {mockRequest,configureMock}=await import('../api/mock-server')
  let posts=0;let lookups=0
  const handler:typeof mockRequest=async(input,init)=>{
   const url=input instanceof Request?input.url:String(input)
   if(url.endsWith('/events/commands')){posts++;return Response.json({error:'服务内部错误'},{status})}
   if(url.includes('/events/commands/'))lookups++
   return mockRequest(input,init)
  }
  const server=mode==='http'?await startHttpStudioFixture(handler):null
  const restore=setStudioTransport(server?fetch:handler)
  const client=new StudioEventClient(server?.origin??'http://autoflow-studio.mock')
  try{
   const commandId=`unknown-${mode}-${status}`
   expect(await client.command('set_verbose_log',{enabled:true},commandId)).toMatchObject({commandId,success:false,status:'unconfirmed'})
   expect(posts).toBe(1);expect(lookups).toBe(1)
  }finally{client.disconnect();configureMock({disconnect:true});await server?.close();restore()}
 })
}
it('does not mistake another command identity in a 409 response for its own rejection',async()=>{
 vi.resetModules();const {mockRequest,configureMock}=await import('../api/mock-server')
 let lookups=0
 const restore=setStudioTransport(async(input,init)=>{
  const url=input instanceof Request?input.url:String(input)
  if(url.endsWith('/events/commands')){
   await mockRequest(input,init)
   return Response.json({commandId:'another-command',success:false,error:'另一条命令的冲突'},{status:409})
  }
  if(url.includes('/events/commands/'))lookups++
  return mockRequest(input,init)
 })
 const client=new StudioEventClient('http://autoflow-studio.mock')
 try{
  expect(await client.command('set_verbose_log',{enabled:true},'own-command')).toMatchObject({commandId:'own-command',success:true})
  expect(lookups).toBe(1)
 }finally{client.disconnect();configureMock({disconnect:true});restore()}
})
it('queries a contradictory successful receipt carried by HTTP 409',async()=>{
 vi.resetModules();const {mockRequest,configureMock}=await import('../api/mock-server')
 let lookups=0
 const restore=setStudioTransport(async(input,init)=>{
  const url=input instanceof Request?input.url:String(input)
  if(url.endsWith('/events/commands')){
   await mockRequest(input,init)
   return Response.json({commandId:'contradictory-command',success:true},{status:409})
  }
  if(url.includes('/events/commands/'))lookups++
  return mockRequest(input,init)
 })
 const client=new StudioEventClient('http://autoflow-studio.mock')
 try{
  expect(await client.command('set_verbose_log',{enabled:true},'contradictory-command')).toMatchObject({commandId:'contradictory-command',success:true,httpStatus:200})
  expect(lookups).toBe(1)
 }finally{client.disconnect();configureMock({disconnect:true});restore()}
})
