import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
vi.hoisted(()=>{const values=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>values.set(key,value),removeItem:(key:string)=>values.delete(key)})})
import {socketService} from '../events'
import {useWorkflowStore as store} from '../editor-store'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
import {parseServerSentEvents} from '../../../shared/api/events'
describe.each(['memory','http'] as const)('speech consumer over %s',mode=>{
 let mock:typeof import('../api/mock-server')
 let server:Awaited<ReturnType<typeof startHttpStudioFixture>>|undefined
 let restore:()=>void
 let execute=vi.fn<(utterance:SpeechSynthesisUtterance)=>void>()
 let cancel=vi.fn<()=>void>()
 let held:boolean
 let calls:Array<{url:string;event?:string}>
 let lose:string|undefined
 let request:(path:string,body?:unknown)=>Promise<Response>
 beforeEach(async()=>{
  const values=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>values.set(key,value),removeItem:(key:string)=>values.delete(key)})
  vi.resetModules();mock=await import('../api/mock-server');if(mode==='http')server=await startHttpStudioFixture(mock.mockRequest)
  held=false;lose=undefined;calls=[];execute=vi.fn();cancel=vi.fn()
  vi.stubGlobal('SpeechSynthesisUtterance',class {
   onend:(()=>void)|null=null;onerror=null;lang='';rate=1;pitch=1;volume=1
   constructor(public text:string){}
  })
  vi.stubGlobal('speechSynthesis',{speak:(utterance:SpeechSynthesisUtterance)=>{execute(utterance);if(!held)queueMicrotask(()=>utterance.onend?.(new Event('end') as SpeechSynthesisEvent))},cancel})
  const transport=async(input:RequestInfo|URL,init?:RequestInit)=>{
   const url=String(input);const body=typeof init?.body==='string'?JSON.parse(init.body):undefined;calls.push({url,event:body?.event})
   if(lose==='state_query' && url.includes('/events/tts-requests/')){lose=undefined;throw new TypeError('Failed to fetch script state')}
   const response=await(server?fetch(input,init):mock.mockRequest(input,init))
   if(body?.event && body.event===lose){lose=undefined;throw new TypeError('Failed to fetch after command applied')}
   return response
  }
  const origin=server?.origin??'http://autoflow-studio.mock'
  restore=configureStudioConnection(origin,transport)
  request=(path,body)=>transport(`${origin}/api${path}`,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
  store.getState().clearWorkflow()
 })
 afterEach(async()=>{if(mock.mockSnapshot().run)await request('/workflows/speech-delivery/stop',{});socketService.disconnect();mock.configureMock({disconnect:true});await server?.close();server=undefined;restore();vi.unstubAllGlobals()})
 async function start(connect=true){
  if(connect){socketService.connect();await vi.waitFor(()=>expect(socketService.isConnected()).toBe(true))}
  await request('/workflows',{id:'speech-delivery',name:'语音消费',nodes:[{id:'voice',type:'text_to_speech',data:{text:'通知',lang:'zh-CN',rate:1,pitch:1,volume:0}}],variables:[]})
  await request('/workflows/speech-delivery/execute',{})
 }
 async function speechEvent(){
  let found:Record<string,unknown>|undefined
  await vi.waitFor(async()=>{
   const count=mock.mockSnapshot().sequence;const response=await request('/events/stream?afterSeq=0');const iterator=parseServerSentEvents(response.body!)[Symbol.asyncIterator]()
   try{for(let i=0;i<count;i++){const event=(await iterator.next()).value!;if(event.event==='execution:tts_request')found=JSON.parse(event.data)}}finally{await iterator.return?.(undefined);await response.body?.cancel()}
   expect(found).toBeDefined()
  },{timeout:2000})
  return found!
 }
 it.each([undefined,'tts_claim','tts_result','state_query'])('executes once and confirms result with lost=%s',async lost=>{
  lose=lost;await start()
  await vi.waitFor(()=>expect(store.getState().executionStatus).toBe('completed'),{timeout:2500})
  expect(execute).toHaveBeenCalledOnce();expect(cancel).not.toHaveBeenCalled()
  expect(execute.mock.calls[0][0]).toMatchObject({text:'通知',volume:0})
  expect(calls.filter(c=>c.event==='tts_claim')).toHaveLength(1)
  expect(calls.filter(c=>c.event==='tts_result')).toHaveLength(1)
  if(lost && lost!=='state_query')expect(calls.some(c=>/\/events\/commands\//.test(c.url))).toBe(true)
  if(lost==='state_query')expect(calls.filter(c=>c.url.includes('/events/tts-requests/'))).toHaveLength(2)
  const old=await speechEvent();mock.emitMockEvent('execution:tts_request',old)
  const marker=vi.fn();socketService.on('speech-marker',marker);mock.emitMockEvent('speech-marker',{})
  await vi.waitFor(()=>expect(marker).toHaveBeenCalledOnce());socketService.off('speech-marker',marker)
  expect(execute).toHaveBeenCalledOnce()
 })
 it('cancels a pending speech when stopped and never submits a result',async()=>{
  held=true;await start();await vi.waitFor(()=>expect(execute).toHaveBeenCalledOnce(),{timeout:2000})
  await request('/workflows/speech-delivery/stop',{})
  await vi.waitFor(()=>expect(cancel).toHaveBeenCalledOnce())
  expect(calls.filter(c=>c.event==='tts_result')).toHaveLength(0)
 })
 it('preserves an active utterance when reconnect is requested during an SSE interruption',async()=>{
  held=true;await start();await vi.waitFor(()=>expect(execute).toHaveBeenCalledOnce(),{timeout:2000})
  const utterance=execute.mock.calls[0][0]
  mock.configureMock({disconnect:true});await vi.waitFor(()=>expect(socketService.isConnected()).toBe(false))
  socketService.connect();await vi.waitFor(()=>expect(socketService.isConnected()).toBe(true),{timeout:2000})
  utterance.onend?.(new Event('end') as SpeechSynthesisEvent)
  await vi.waitFor(()=>expect(store.getState().executionStatus).toBe('completed'),{timeout:2000})
  expect(execute).toHaveBeenCalledOnce();expect(calls.filter(c=>c.event==='tts_result')).toHaveLength(1)
 })
 it('rejects a malformed speech event without speaking',async()=>{
  socketService.connect();await vi.waitFor(()=>expect(socketService.isConnected()).toBe(true))
  mock.emitMockEvent('execution:tts_request',null)
  await vi.waitFor(()=>expect(store.getState().logs.some(log=>log.message.includes('语音请求缺少有效身份'))).toBe(true))
  expect(execute).not.toHaveBeenCalled()
 })
 it('does not replay speech already claimed by another page',async()=>{
  await start(false);const event=await speechEvent()
  await request('/events/commands',{commandId:'other-claim-command',event:'tts_claim',data:{requestId:event.requestId,claimId:'other-page'}})
  socketService.connect()
  await vi.waitFor(()=>expect(store.getState().logs.some(log=>log.message.includes('语音已被领取'))).toBe(true),{timeout:2000})
  expect(execute).not.toHaveBeenCalled()
 })
})
