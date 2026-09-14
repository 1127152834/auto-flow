import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
import {parseServerSentEvents} from '../../../shared/api/events'
describe.each(['memory','http'] as const)('speech protocol over %s',mode=>{
 let mock:typeof import('../api/mock-server');let server:Awaited<ReturnType<typeof startHttpStudioFixture>>|undefined
 let request:(path:string,body?:unknown,method?:string)=>Promise<Response>
 beforeEach(async()=>{
  const storage=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>storage.get(key)??null,setItem:(key:string,value:string)=>storage.set(key,value)})
  vi.resetModules();mock=await import('../api/mock-server');if(mode==='http')server=await startHttpStudioFixture(mock.mockRequest)
  request=(path,body,method)=>{const init={method:method??(body===undefined?'GET':'POST'),headers:{'Content-Type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)})};return server?fetch(`${server.origin}/api${path}`,init):mock.mockRequest(`http://autoflow-studio.mock/api${path}`,init)}
 })
 afterEach(async()=>{if(mock.mockSnapshot().run)await request('/workflows/speech-protocol/stop',{});mock.configureMock({disconnect:true});await server?.close();server=undefined;vi.unstubAllGlobals()})
 async function journal(){
  const count=mock.mockSnapshot().sequence;const response=await request('/events/stream?afterSeq=0');const iterator=parseServerSentEvents(response.body!)[Symbol.asyncIterator]();const result:Array<{event:string;data:Record<string,unknown>}>=[]
  try{for(let i=0;i<count;i++){const item=(await iterator.next()).value!;result.push({event:item.event,data:JSON.parse(item.data)})}}finally{await iterator.return?.(undefined);await response.body?.cancel()}
  return result
 }
 async function start(volume:unknown=0){
  await request('/workflows',{id:'speech-protocol',nodes:[{id:'voice',type:'text_to_speech',data:{text:'通知',volume}},{id:'after',type:'open_page'}]})
  await request('/workflows/speech-protocol/execute',{})
 }
 async function pending(){
  await start();let payload:Record<string,unknown>|undefined
  await vi.waitFor(async()=>{payload=(await journal()).find(item=>item.event==='execution:tts_request')?.data;expect(payload).toBeDefined()},{timeout:1500})
  expect(payload).toMatchObject({workflowId:'speech-protocol',nodeId:'voice',text:'通知',lang:'zh-CN',rate:1,pitch:1,volume:0})
  return {requestId:payload!.requestId,claimId:'owner'}
 }
 const command=(event:string,data:unknown,commandId:string)=>request('/events/commands',{event,data,commandId})
 it('requires ownership and confirms repeated result commands without repeating the next node',async()=>{
  const identity=await pending();expect((await command('tts_claim',identity,'claim')).status).toBe(200);expect((await command('tts_claim',identity,'claim')).status).toBe(200)
  expect((await command('tts_claim',{...identity,claimId:'other'},'claim')).status).toBe(409)
  expect((await command('tts_claim',{...identity,claimId:'other'},'other-claim')).status).toBe(409)
  expect(await(await request(`/events/tts-requests/${identity.requestId}`)).json()).toMatchObject({...identity,status:'claimed'})
  const result={...identity,success:true,error:null};expect((await command('tts_result',result,'result')).status).toBe(200);expect((await command('tts_result',result,'result')).status).toBe(200)
  await vi.waitFor(()=>expect(mock.mockSnapshot().run).toBeNull())
  expect((await journal()).filter(item=>item.event==='execution:node_complete').map(item=>item.data.nodeId)).toEqual(['voice','after'])
  expect(await(await request(`/events/tts-requests/${identity.requestId}`)).json()).toMatchObject({status:'completed'})
  expect((await command('tts_result',result,'new-result')).status).toBe(409)
 })
 it('rejects unclaimed, foreign and malformed results without consuming the request',async()=>{
  const identity=await pending();expect((await command('tts_result',{...identity,success:true},'unclaimed')).status).toBe(409)
  await command('tts_claim',identity,'claim')
  for(const [index,result] of [{...identity,success:false},{...identity,success:'true'}].entries())expect((await command('tts_result',result,`invalid-${index}`)).status).toBe(422)
  expect((await command('tts_result',{...identity,claimId:'other',success:true},'foreign')).status).toBe(409)
  expect(mock.mockSnapshot().run).toBe('speech-protocol');expect((await journal()).some(item=>item.event==='execution:node_complete')).toBe(false)
 })
 it('retains a speech failure and never schedules the next node',async()=>{
  const identity=await pending();await command('tts_claim',identity,'claim');expect((await command('tts_result',{...identity,success:false,error:'语音不可用'},'error')).status).toBe(200)
  expect(mock.mockSnapshot().run).toBeNull();expect((await journal()).filter(item=>item.event==='execution:node_start').map(item=>item.data.nodeId)).toEqual(['voice'])
  expect(await(await request(`/events/tts-requests/${identity.requestId}`)).json()).toMatchObject({status:'failed'})
 })
 it('expires on stop and rejects late speech acknowledgements',async()=>{
  const identity=await pending();await command('tts_claim',identity,'claim');await request('/workflows/speech-protocol/stop',{})
  expect(await(await request(`/events/tts-requests/${identity.requestId}`)).json()).toMatchObject({status:'expired'})
  const sequence=mock.mockSnapshot().sequence;expect((await command('tts_result',{...identity,success:true},'late')).status).toBe(409);expect(mock.mockSnapshot().sequence).toBe(sequence)
 })
 it('rejects unknown requests and mutation methods on state queries',async()=>{
  expect((await request('/events/tts-requests/missing')).status).toBe(404)
  const identity=await pending();expect((await request(`/events/tts-requests/${identity.requestId}`,{})).status).toBe(405)
 })
 it('rejects explicit invalid volume instead of replacing it with a default',async()=>{
  await start(2);await vi.waitFor(()=>expect(mock.mockSnapshot().run).toBeNull())
  const events=await journal();expect(events.some(item=>item.event==='execution:tts_request')).toBe(false)
  expect(events.filter(item=>item.event==='execution:node_complete').map(item=>item.data)).toEqual([{workflowId:'speech-protocol',nodeId:'voice',success:false}])
 })
})
