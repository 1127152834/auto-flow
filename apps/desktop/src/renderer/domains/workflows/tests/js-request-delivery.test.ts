import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
vi.hoisted(()=>{const values=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>values.set(key,value),removeItem:(key:string)=>values.delete(key)})})
import {socketService} from '../events'
import {useWorkflowStore as store} from '../editor-store'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
import {evaluateJsScript} from '../lib/jsScript'
import {parseServerSentEvents} from '../../../shared/api/events'
describe.each(['memory','http'] as const)('script consumer over %s',mode=>{
 let mock:typeof import('../api/mock-server')
 let server:Awaited<ReturnType<typeof startHttpStudioFixture>>|undefined
 let restore:()=>void
 let execute=vi.fn<(data:{code:string;variables:Record<string,unknown>})=>void>()
 let terminate=vi.fn<()=>void>()
 let held:boolean
 let calls:Array<{url:string;event?:string}>
 let lose:string|undefined
 let request:(path:string,body?:unknown)=>Promise<Response>
 beforeEach(async()=>{
  const values=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>values.set(key,value),removeItem:(key:string)=>values.delete(key)})
  vi.resetModules();mock=await import('../api/mock-server');if(mode==='http')server=await startHttpStudioFixture(mock.mockRequest)
  held=false;lose=undefined;calls=[];execute=vi.fn();terminate=vi.fn()
  vi.stubGlobal('Worker',class {
   onmessage:((event:{data:unknown})=>void)|null=null
   onerror=null
   postMessage(data:{code:string;variables:Record<string,unknown>}){execute(data);if(!held)queueMicrotask(()=>this.onmessage?.({data:evaluateJsScript(data.code,data.variables)}))}
   terminate=terminate
  })
  const transport=async(input:RequestInfo|URL,init?:RequestInit)=>{
   const url=String(input);const body=typeof init?.body==='string'?JSON.parse(init.body):undefined;calls.push({url,event:body?.event})
   if(lose==='state_query' && url.includes('/events/js-requests/')){lose=undefined;throw new TypeError('Failed to fetch script state')}
   const response=await(server?fetch(input,init):mock.mockRequest(input,init))
   if(body?.event && body.event===lose){lose=undefined;throw new TypeError('Failed to fetch after command applied')}
   return response
  }
  const origin=server?.origin??'http://autoflow-studio.mock'
  restore=configureStudioConnection(origin,transport)
  request=(path,body)=>transport(`${origin}/api${path}`,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
  store.getState().clearWorkflow()
 })
 afterEach(async()=>{if(mock.mockSnapshot().run)await request('/workflows/js-delivery/stop',{});socketService.disconnect();mock.configureMock({disconnect:true});await server?.close();server=undefined;restore();vi.unstubAllGlobals()})
 async function start(connect=true){
  if(connect){socketService.connect();await vi.waitFor(()=>expect(socketService.isConnected()).toBe(true))}
  await request('/workflows',{id:'js-delivery',name:'脚本消费',nodes:[{id:'script',type:'js_script',data:{code:'function main(vars){vars.count++;return vars.count}',resultVariable:'answer'}}],variables:[{name:'count',value:1}]})
  await request('/workflows/js-delivery/execute',{})
 }
 async function scriptEvent(){
  let found:Record<string,unknown>|undefined
  await vi.waitFor(async()=>{
   const count=mock.mockSnapshot().sequence;const response=await request('/events/stream?afterSeq=0');const iterator=parseServerSentEvents(response.body!)[Symbol.asyncIterator]()
   try{for(let i=0;i<count;i++){const event=(await iterator.next()).value!;if(event.event==='execution:js_script')found=JSON.parse(event.data)}}finally{await iterator.return?.(undefined);await response.body?.cancel()}
   expect(found).toBeDefined()
  },{timeout:2000})
  return found!
 }
 it.each([undefined,'js_script_claim','js_script_result','state_query'])('executes once and confirms result with lost=%s',async lost=>{
  lose=lost;await start()
  await vi.waitFor(()=>expect(store.getState().executionStatus).toBe('completed'),{timeout:2500})
  expect(execute).toHaveBeenCalledOnce();expect(terminate).toHaveBeenCalledOnce()
  expect((await(await request('/workflows/global-variables')).json()).variables).toEqual({count:2,answer:2})
  expect(calls.filter(c=>c.event==='js_script_claim')).toHaveLength(1)
  expect(calls.filter(c=>c.event==='js_script_result')).toHaveLength(1)
  if(lost && lost!=='state_query')expect(calls.some(c=>/\/events\/commands\//.test(c.url))).toBe(true)
  if(lost==='state_query')expect(calls.filter(c=>c.url.includes('/events/js-requests/'))).toHaveLength(2)
  const old=await scriptEvent();mock.emitMockEvent('execution:js_script',old)
  const marker=vi.fn();socketService.on('script-marker',marker);mock.emitMockEvent('script-marker',{})
  await vi.waitFor(()=>expect(marker).toHaveBeenCalledOnce());socketService.off('script-marker',marker)
  expect(execute).toHaveBeenCalledOnce()
 })
 it('terminates a pending script when stopped and never submits a result',async()=>{
  held=true;await start();await vi.waitFor(()=>expect(execute).toHaveBeenCalledOnce(),{timeout:2000})
  await request('/workflows/js-delivery/stop',{})
  await vi.waitFor(()=>expect(terminate).toHaveBeenCalledOnce())
  expect(calls.filter(c=>c.event==='js_script_result')).toHaveLength(0)
 })
 it('rejects a malformed script event without starting a worker',async()=>{
  socketService.connect();await vi.waitFor(()=>expect(socketService.isConnected()).toBe(true))
  mock.emitMockEvent('execution:js_script',null)
  await vi.waitFor(()=>expect(store.getState().logs.some(log=>log.message.includes('脚本请求缺少有效身份'))).toBe(true))
  expect(execute).not.toHaveBeenCalled()
 })
 it('does not replay a script already claimed by another page',async()=>{
  await start(false);const event=await scriptEvent()
  await request('/events/commands',{commandId:'other-claim-command',event:'js_script_claim',data:{requestId:event.requestId,claimId:'other-page'}})
  socketService.connect()
  await vi.waitFor(()=>expect(store.getState().logs.some(log=>log.message.includes('脚本已被领取'))).toBe(true),{timeout:2000})
  expect(execute).not.toHaveBeenCalled()
 })
})
