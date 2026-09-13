import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
import {parseServerSentEvents} from '../../../shared/api/events'

describe.each(['memory','http'])('input command protocol over %s',mode=>{
 let server:typeof import('../api/mock-server')
 let fixture:Awaited<ReturnType<typeof startHttpStudioFixture>>|undefined
 let request:(path:string,body?:unknown)=>Promise<Response>
 beforeEach(async()=>{
  const values=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>values.set(key,value)})
  vi.resetModules();server=await import('../api/mock-server')
  if(mode==='http')fixture=await startHttpStudioFixture(server.mockRequest)
  request=(path,body)=>{const init=body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)};return fixture?fetch(`${fixture.origin}/api${path}`,init):server.mockRequest(`http://autoflow-studio.mock/api${path}`,init)}
 })
 afterEach(async()=>{if(server.mockSnapshot().run)await request('/workflows/input-run/stop',{});server.configureMock({disconnect:true});await fixture?.close();fixture=undefined;vi.unstubAllGlobals()})
 async function journal(){
  const count=server.mockSnapshot().sequence;const response=await request('/events/stream?afterSeq=0');const iterator=parseServerSentEvents(response.body!)[Symbol.asyncIterator]();const result:Array<{event:string,data:Record<string,unknown>}>=[]
  try{for(let i=0;i<count;i++){const item=(await iterator.next()).value!;result.push({event:item.event,data:JSON.parse(item.data)})}}finally{await iterator.return?.(undefined);await response.body?.cancel()}
  return result
 }
 async function start(inputMode='single'){
  await request('/workflows',{id:'input-run',name:'输入命令验收',nodes:[{id:'prompt',type:'input_prompt',data:{variableName:'answer',inputMode,promptTitle:'输入协议',defaultValue:''}},{id:'after',type:'open_page'}],variables:[{name:'answer',value:'original'}]})
  await request('/workflows/input-run/execute',{})
  let prompt:Record<string,unknown>|undefined
  await vi.waitFor(async()=>{prompt=(await journal()).find(e=>e.event==='execution:input_prompt')?.data;expect(prompt).toBeDefined()},{timeout:1000})
  return prompt!
 }
 const command=(requestId:unknown,value:unknown,commandId='input-command')=>request('/events/commands',{commandId,event:'input_prompt_result',data:{requestId,value}})
 it.each([['single','text','text'],['number','2.5',2.5],['integer','2',2],['checkbox','false',false],['list','甲\n乙',['甲','乙']],['select_multiple','["甲","乙"]',['甲','乙']]] as const)('waits for %s input, applies it once and resumes subsequent nodes',async(inputMode,value,expected)=>{
  const prompt=await start(inputMode);expect((await journal()).some(e=>e.event==='execution:node_complete')).toBe(false)
  expect((await command(prompt.requestId,value)).status).toBe(200)
  expect((await command(prompt.requestId,value)).status).toBe(200)
  await vi.waitFor(()=>expect(server.mockSnapshot().run).toBeNull(),{timeout:2000})
  expect((await (await request('/workflows/global-variables')).json()).variables.answer).toEqual(expected)
  expect((await journal()).filter(e=>e.event==='execution:node_complete').map(e=>e.data.nodeId)).toEqual(['prompt','after'])
  expect(await (await request('/events/commands/input-command')).json()).toMatchObject({commandId:'input-command',success:true,httpStatus:200})
 })
 it('cancels with null, retains the existing variable and continues the source-defined path',async()=>{
  const prompt=await start();expect((await command(prompt.requestId,null)).status).toBe(200)
  await vi.waitFor(()=>expect(server.mockSnapshot().run).toBeNull(),{timeout:2000})
  expect((await (await request('/workflows/global-variables')).json()).variables.answer).toBe('original')
 })
 it('rejects an unknown request and malformed value without completing the pending node',async()=>{
  const prompt=await start();const before=server.mockSnapshot().sequence
  expect((await command('stale','wrong','stale-command')).status).toBe(409)
  expect((await command(prompt.requestId,{invalid:true},'bad-command')).status).toBe(422)
  expect(server.mockSnapshot()).toMatchObject({run:'input-run',sequence:before})
 })
 it('rejects a consumed request under a new command identity',async()=>{
  const prompt=await start();await command(prompt.requestId,'once')
  expect((await command(prompt.requestId,'twice','new-command')).status).toBe(409)
 })
 it('rejects input after stop and does not schedule subsequent nodes',async()=>{
  const prompt=await start();await request('/workflows/input-run/stop',{});const before=server.mockSnapshot().sequence
  expect((await command(prompt.requestId,'late')).status).toBe(409)
  expect(server.mockSnapshot()).toMatchObject({run:null,sequence:before})
  expect((await journal()).filter(e=>e.event==='execution:node_start').map(e=>e.data.nodeId)).toEqual(['prompt'])
 })
 it.each(['answered','cancelled','expired'] as const)('queries pending input and its %s terminal state without exposing values',async status=>{
  const prompt=await start()
  const path=`/events/input-prompts/${prompt.requestId}`
  expect(await(await request(path)).json()).toEqual({requestId:prompt.requestId,workflowId:'input-run',nodeId:'prompt',status:'pending'})
  if(status==='expired')await request('/workflows/input-run/stop',{})
  else await command(prompt.requestId,status==='cancelled'?null:'private-value')
  expect(await(await request(path)).json()).toEqual({requestId:prompt.requestId,workflowId:'input-run',nodeId:'prompt',status})
  expect((await request(path,{})).status).toBe(405)
 })
 it('reports unknown input identities as missing',async()=>{
  expect((await request('/events/input-prompts/unknown')).status).toBe(404)
 })
 it('rejects unimplemented commands explicitly and makes the rejection queryable',async()=>{
  const payload={commandId:'unsupported',event:'not_implemented',data:{}}
  expect((await request('/events/commands',payload)).status).toBe(501)
  expect(await (await request('/events/commands/unsupported')).json()).toMatchObject({commandId:'unsupported',success:false,httpStatus:501})
  expect((await request('/events/commands',payload)).status).toBe(501)
 })
 it.each([['set_verbose_log',{enabled:'true'}],['set_current_workflow',{workflowId:1}]])('rejects malformed %s metadata',async(event,data)=>{
  expect((await request('/events/commands',{commandId:'malformed',event,data})).status).toBe(422)
 })

})
