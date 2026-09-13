import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
import {parseServerSentEvents} from '../../../shared/api/events'
describe.each(['memory','http'] as const)('JavaScript request over %s',mode=>{
 let mock:typeof import('../api/mock-server')
 let server:Awaited<ReturnType<typeof startHttpStudioFixture>>|undefined
 let request:(path:string,body?:unknown)=>Promise<Response>
 beforeEach(async()=>{
  const data=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value)})
  vi.resetModules();mock=await import('../api/mock-server');if(mode==='http')server=await startHttpStudioFixture(mock.mockRequest)
  request=(path,body)=>{const init=body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)};return server?fetch(`${server.origin}/api${path}`,init):mock.mockRequest(`http://autoflow-studio.mock/api${path}`,init)}
 })
 afterEach(async()=>{if(mock.mockSnapshot().run)await request('/workflows/js-run/stop',{});mock.configureMock({disconnect:true});await server?.close();server=undefined;vi.unstubAllGlobals()})
 async function journal(){
  const count=mock.mockSnapshot().sequence;const response=await request('/events/stream?afterSeq=0');const iterator=parseServerSentEvents(response.body!)[Symbol.asyncIterator]();const entries:Array<{event:string,data:Record<string,unknown>}>=[]
  try{for(let i=0;i<count;i++){const e=(await iterator.next()).value!;entries.push({event:e.event,data:JSON.parse(e.data)})}}finally{await iterator.return?.(undefined);await response.body?.cancel()}
  return entries
 }
 async function start(){
  await request('/workflows',{id:'js-run',name:'脚本协议',nodes:[{id:'script',type:'js_script',data:{code:'function main(vars){vars.count++;return vars.count}',resultVariable:'answer'}},{id:'after',type:'open_page'}],variables:[{name:'count',value:1}]})
  await request('/workflows/js-run/execute',{})
  let event:Record<string,unknown>|undefined
  await vi.waitFor(async()=>{event=(await journal()).find(e=>e.event==='execution:js_script')?.data;expect(event).toBeDefined()},{timeout:1200})
  return event!
 }
 const command=(event:string,data:unknown,commandId:string)=>request('/events/commands',{event,data,commandId})
 it('claims once, applies confirmed result and existing variables, then continues once',async()=>{
  const event=await start();expect(event).toMatchObject({workflowId:'js-run',nodeId:'script',variables:{count:1}})
  const payload={requestId:event.requestId,claimId:'owner'}
  expect((await command('js_script_claim',payload,'claim')).status).toBe(200)
  expect((await command('js_script_claim',payload,'claim')).status).toBe(200)
  expect((await command('js_script_claim',{...payload,claimId:'other'},'other-claim')).status).toBe(409)
  expect(await(await request(`/events/js-requests/${event.requestId}`)).json()).toMatchObject({...payload,status:'claimed'})
  const result={...payload,success:true,result:{value:2},variables:{count:2,notDeclared:99}}
  expect((await command('js_script_result',result,'result')).status).toBe(200)
  expect((await command('js_script_result',result,'result')).status).toBe(200)
  expect((await command('js_script_result',result,'new-result')).status).toBe(409)
  await vi.waitFor(()=>expect(mock.mockSnapshot().run).toBeNull())
  expect((await(await request('/workflows/global-variables')).json()).variables).toEqual({count:2,answer:{value:2}})
  expect((await journal()).filter(e=>e.event==='execution:node_complete').map(e=>e.data.nodeId)).toEqual(['script','after'])
  expect((await(await request('/workflows/js-run/variable-tracking')).json()).tracking).toEqual(expect.arrayContaining([
   expect.objectContaining({variable_name:'count',old_value:1,new_value:2,node_id:'script',operation:'update'}),
   expect.objectContaining({variable_name:'answer',new_value:{value:2},node_id:'script',operation:'create'}),
  ]))
  expect(await(await request('/events/commands/result')).json()).toMatchObject({commandId:'result',success:true,httpStatus:200})
 })
 it('continues tracking new changes after clearing an active run',async()=>{
  const event=await start();const payload={requestId:event.requestId,claimId:'clear-owner'}
  const url=`${server?.origin??'http://autoflow-studio.mock'}/api/workflows/js-run/variable-tracking`
  expect((await (server?fetch:mock.mockRequest)(url,{method:'DELETE'})).status).toBe(200)
  expect(await(await request('/workflows/js-run/variable-tracking')).json()).toMatchObject({tracking:[],count:0})
  await command('js_script_claim',payload,'clear-claim')
  await command('js_script_result',{...payload,success:true,result:2,variables:{count:2}},'clear-result')
  const result=await(await request('/workflows/js-run/variable-tracking')).json()
  expect(result.count).toBe(2)
  expect(result.tracking.map((row:{variable_name:string})=>row.variable_name)).toEqual(['count','answer'])
 })
 it('rejects malformed results and foreign claims without consuming the waiting request',async()=>{
  const event=await start();const payload={requestId:event.requestId,claimId:'owner'}
  await command('js_script_claim',payload,'claim')
  expect((await command('js_script_result',{...payload,success:true,result:1},'missing-variables')).status).toBe(422)
  expect((await command('js_script_result',{...payload,claimId:'other',success:true,result:1,variables:{}},'foreign')).status).toBe(409)
  expect((await command('js_script_result',{...payload,success:false},'missing-error')).status).toBe(422)
  expect(mock.mockSnapshot().run).toBe('js-run')
  expect((await journal()).some(e=>e.event==='execution:node_complete')).toBe(false)
 })
 it('records script failure without executing the following node',async()=>{
  const event=await start();const payload={requestId:event.requestId,claimId:'owner'};await command('js_script_claim',payload,'claim')
  expect((await command('js_script_result',{...payload,success:false,error:'脚本错误'},'failure')).status).toBe(200)
  expect(mock.mockSnapshot().run).toBeNull()
  expect(await(await request(`/events/js-requests/${event.requestId}`)).json()).toMatchObject({status:'failed'})
  expect((await journal()).filter(e=>e.event==='execution:node_start').map(e=>e.data.nodeId)).toEqual(['script'])
 })
 it('expires after stop and rejects a late result or claim',async()=>{
  const event=await start();await request('/workflows/js-run/stop',{});const before=mock.mockSnapshot().sequence
  expect((await command('js_script_claim',{requestId:event.requestId,claimId:'late'},'claim')).status).toBe(409)
  expect((await command('js_script_result',{requestId:event.requestId,claimId:'late',success:true,variables:{}},'result')).status).toBe(409)
  expect(mock.mockSnapshot().sequence).toBe(before)
  expect(await(await request(`/events/js-requests/${event.requestId}`)).json()).toMatchObject({status:'expired'})
 })
 it('retains results larger than 64 KiB through command confirmation and later reads',async()=>{
  const event=await start();const payload={requestId:event.requestId,claimId:'large-owner'}
  await command('js_script_claim',payload,'large-claim')
  const value='数据'.repeat(40000)
  expect((await command('js_script_result',{...payload,success:true,result:value,variables:{count:2}},'large-result')).status).toBe(200)
  await vi.waitFor(()=>expect(mock.mockSnapshot().run).toBeNull())
  expect((await(await request('/workflows/global-variables')).json()).variables.answer).toBe(value)
  expect((await(await request('/workflows/js-run/variable-tracking')).json()).tracking.find((row:{variable_name:string})=>row.variable_name==='answer').new_value).toBe(value)
 })
 it('rejects unknown queries and wrong query methods',async()=>{
  expect((await request('/events/js-requests/missing')).status).toBe(404)
  const event=await start();expect((await request(`/events/js-requests/${event.requestId}`,{})).status).toBe(405)
 })
})
