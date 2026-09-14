import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
describe.each(['memory','http'])('pause-bound debug commands over %s',mode=>{
 let service:typeof import('../api/mock-server')
 let fixture:Awaited<ReturnType<typeof startHttpStudioFixture>>|undefined
 let request:(path:string,body?:unknown,method?:string)=>Promise<Response>
 let pause:{pauseId:string;controlRevision:number}
 beforeEach(async()=>{
  const data=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value)})
  vi.resetModules();service=await import('../api/mock-server')
  if(mode==='http')fixture=await startHttpStudioFixture(service.mockRequest)
  request=(path,body={},method='POST')=>{
   const init={method,...(method==='GET'?{}:{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})}
   return fixture?fetch(`${fixture.origin}/api${path}`,init):service.mockRequest(`http://autoflow-studio.mock/api${path}`,init)
  }
  await request('/workflows',{id:'pause-test',nodes:[{id:'a',type:'open_page'},{id:'b',type:'open_page'},{id:'c',type:'open_page'}],variables:[]})
  await request('/workflows/pause-test/execute',{stepMode:true})
  await vi.waitFor(()=>expect(service.mockSnapshot().pause?.pauseId).toBeTruthy())
  pause=service.mockSnapshot().pause!
 })
 afterEach(async()=>{if(service?.mockSnapshot().run)await request('/workflows/pause-test/stop');service?.configureMock({disconnect:true});await fixture?.close();fixture=undefined;vi.unstubAllGlobals()})
 it('applies simultaneous identical steps once and retains the first receipt after moving to the next pause',async()=>{
  const body={commandId:'same-step',...pause}
  const responses=await Promise.all([request('/workflows/pause-test/debug/step',body),request('/workflows/pause-test/debug/step',body)])
  expect(responses.map(response=>response.status)).toEqual([200,200])
  const receipts=await Promise.all(responses.map(response=>response.json()));expect(receipts[1]).toEqual(receipts[0])
  await vi.waitFor(()=>{expect(service.mockSnapshot().pause).toBeTruthy();expect(service.mockSnapshot().pause?.pauseId).not.toBe(pause.pauseId)})
  const next=service.mockSnapshot();expect(next.pause).toBeTruthy()
  expect((await request('/workflows/pause-test/debug/step',body)).status).toBe(200)
  expect(service.mockSnapshot()).toEqual(next)
  const lookup=await request('/events/commands/same-step',{},'GET')
  expect(await lookup.json()).toMatchObject({...body,workflowId:'pause-test',action:'step',success:true,httpStatus:200})
  await request('/workflows/pause-test/stop')
  expect(service.mockSnapshot().run).toBeNull()
  expect((await request('/workflows/pause-test/debug/step',body)).status).toBe(200)
  expect(await (await request('/events/commands/same-step',{},'GET')).json()).toMatchObject({...body,success:true,httpStatus:200})
  expect(service.mockSnapshot().run).toBeNull()
 })
 it('rejects another command from an old pause even when the workflow stays active',async()=>{
  await request('/workflows/pause-test/debug/step',{commandId:'first',...pause})
  await vi.waitFor(()=>{expect(service.mockSnapshot().pause).toBeTruthy();expect(service.mockSnapshot().pause?.pauseId).not.toBe(pause.pauseId)})
  const snapshot=service.mockSnapshot()
  expect((await request('/workflows/pause-test/debug/step',{commandId:'late',...pause})).status).toBe(409)
  expect(service.mockSnapshot()).toEqual(snapshot)
 })
 it('rejects the wrong revision and a conflicting command ID without another transition',async()=>{
  expect((await request('/workflows/pause-test/debug/step',{commandId:'revision',...pause,controlRevision:pause.controlRevision+1})).status).toBe(409)
  const snapshot=service.mockSnapshot()
  expect((await request('/workflows/pause-test/debug/resume',{commandId:'revision',...pause})).status).toBe(409)
  expect(service.mockSnapshot()).toEqual(snapshot)
 })
 it.each([{}, {commandId:'x'}, {commandId:'x',pauseId:'x',controlRevision:'1'}])('rejects invalid command context %# before scheduling',async body=>{
  const snapshot=service.mockSnapshot()
  expect((await request('/workflows/pause-test/debug/step',body)).status).toBe(422)
  expect(service.mockSnapshot()).toEqual(snapshot)
 })
})
