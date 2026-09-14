import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {startHttpStudioFixture} from './fixtures/http-studio-server'

describe.each(['memory','http'])('paused variable edits over %s',mode=>{
  let service:typeof import('../api/mock-server')
  let fixture:Awaited<ReturnType<typeof startHttpStudioFixture>>|undefined
  let request:(path:string,body?:unknown,method?:string)=>Promise<Response>

  beforeEach(async()=>{
    const data=new Map<string,string>()
    vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value)})
    vi.resetModules();service=await import('../api/mock-server')
    if(mode==='http')fixture=await startHttpStudioFixture(service.mockRequest)
    request=(path,body={},method='POST')=>{
      const init={method,...(method==='GET'?{}:{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})}
      return fixture?fetch(`${fixture.origin}/api${path}`,init):service.mockRequest(`http://autoflow-studio.mock/api${path}`,init)
    }
    await request('/workflows',{id:'variables-test',nodes:[{id:'a',type:'open_page'}],variables:[{name:'count',value:1}]})
    await request('/workflows/variables-test/execute',{stepMode:true,runId:'variables-run'})
    await vi.waitFor(()=>expect(service.mockSnapshot().pause?.pauseId).toBeTruthy())
  })

  afterEach(async()=>{
    if(service?.mockSnapshot().run)await request('/workflows/variables-test/stop')
    service?.configureMock({disconnect:true});await fixture?.close();fixture=undefined;vi.unstubAllGlobals()
  })

  it('applies an identified batch once and emits a newer pause snapshot',async()=>{
    const pause=service.mockSnapshot().pause!
    const body={commandId:'variables-command',...pause,changes:[{name:'count',value:2},{name:'items',value:['first']}]}
    const responses=await Promise.all([request('/workflows/variables-test/debug/variables',body),request('/workflows/variables-test/debug/variables',body)])
    expect(responses.map(response=>response.status)).toEqual([200,200])
    expect(await responses[1].json()).toEqual(await responses[0].json())
    await vi.waitFor(()=>expect(service.mockSnapshot().pause?.controlRevision).toBe(pause.controlRevision+1))
    const variables=await (await request('/workflows/global-variables',{},'GET')).json()
    expect(variables).toMatchObject({variables:{count:2,items:['first']},count:2})
    const tracking=await (await request('/workflows/variables-test/variable-tracking',{},'GET')).json()
    expect(tracking.tracking).toEqual(expect.arrayContaining([
      expect.objectContaining({variable_name:'count',old_value:1,new_value:2,operation:'update'}),
      expect.objectContaining({variable_name:'items',old_value:null,new_value:['first'],operation:'create'}),
    ]))
    const trackingCount=tracking.tracking.length
    expect((await request('/workflows/variables-test/debug/variables',body)).status).toBe(200)
    expect((await (await request('/workflows/variables-test/variable-tracking',{},'GET')).json()).tracking).toHaveLength(trackingCount)
  })

  it('rejects stale identity, invalid data and conflicting command reuse without mutation',async()=>{
    const pause=service.mockSnapshot().pause!
    expect((await request('/workflows/variables-test/debug/variables',{commandId:'stale',...pause,runId:'older-run',changes:[{name:'count',value:9}]})).status).toBe(409)
    expect((await request('/workflows/variables-test/debug/variables',{commandId:'bad',...pause,changes:[{name:'1bad',value:9}]})).status).toBe(422)
    const accepted={commandId:'once',...pause,changes:[{name:'count',value:3}]}
    expect((await request('/workflows/variables-test/debug/variables',accepted)).status).toBe(200)
    expect((await request('/workflows/variables-test/debug/variables',{...accepted,changes:[{name:'count',value:4}]})).status).toBe(409)
    expect(await (await request('/workflows/global-variables',{},'GET')).json()).toMatchObject({variables:{count:3}})
  })
})
